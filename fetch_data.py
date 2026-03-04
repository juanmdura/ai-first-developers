#!/usr/bin/env python3
"""
Fetch Cursor AI analytics data via the Admin API and generate data/cursor_usage.js for the dashboard.

Uses /teams/daily-usage-data (Basic Auth, 30-day max window).
Aggregates per-user rows into daily team totals.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API_BASE = "https://api.cursor.com"
DEFAULT_START = "2025-08-28"
DEFAULT_END = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MAX_WINDOW_DAYS = 30


def load_api_key():
    key = os.environ.get("CURSOR_API_TOKEN")
    if key:
        return key
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("CURSOR_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("Error: CURSOR_API_TOKEN not found in environment or .env file", file=sys.stderr)
    sys.exit(1)


def api_get(path, api_key, params=None):
    resp = requests.get(f"{API_BASE}{path}", auth=(api_key, ""), params=params)
    resp.raise_for_status()
    return resp.json()


def api_post(path, api_key, body):
    resp = requests.post(f"{API_BASE}{path}", auth=(api_key, ""), json=body)
    resp.raise_for_status()
    return resp.json()


def date_to_epoch_ms(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d").timestamp() * 1000)


def fetch_daily_usage(api_key, start_date, end_date):
    """Fetch /teams/daily-usage-data in <=30-day chunks."""
    all_rows = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    while current < end:
        chunk_end = min(current + timedelta(days=MAX_WINDOW_DAYS), end)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(chunk_end.timestamp() * 1000)

        print(f"  Fetching {current.strftime('%Y-%m-%d')} → {chunk_end.strftime('%Y-%m-%d')} ...", end=" ")
        result = api_post("/teams/daily-usage-data", api_key, {
            "startDate": start_ms,
            "endDate": end_ms,
        })
        rows = result.get("data", [])
        print(f"{len(rows)} rows")
        all_rows.extend(rows)

        current = chunk_end
        if current < end:
            time.sleep(0.5)

    return all_rows


def aggregate_daily(rows):
    """Aggregate per-user rows into daily team totals."""
    daily = {}
    for r in rows:
        day = r["day"]
        if day not in daily:
            daily[day] = {
                "date": day,
                "totalLinesAdded": 0,
                "totalLinesDeleted": 0,
                "acceptedLinesAdded": 0,
                "acceptedLinesDeleted": 0,
                "totalApplies": 0,
                "totalAccepts": 0,
                "totalRejects": 0,
                "totalTabsShown": 0,
                "totalTabsAccepted": 0,
                "composerRequests": 0,
                "chatRequests": 0,
                "agentRequests": 0,
                "cmdkUsages": 0,
                "bugbotUsages": 0,
                "_activeUsers": set(),
            }
        d = daily[day]
        for field in [
            "totalLinesAdded", "totalLinesDeleted",
            "acceptedLinesAdded", "acceptedLinesDeleted",
            "totalApplies", "totalAccepts", "totalRejects",
            "totalTabsShown", "totalTabsAccepted",
            "composerRequests", "chatRequests", "agentRequests",
            "cmdkUsages", "bugbotUsages",
        ]:
            d[field] += r.get(field, 0)
        if r.get("isActive", False) or r.get("totalLinesAdded", 0) > 0:
            d["_activeUsers"].add(r.get("email", r.get("userId")))

    result = []
    for day in sorted(daily.keys()):
        d = daily[day]
        ai_added = d["acceptedLinesAdded"]
        ai_deleted = d["acceptedLinesDeleted"]
        non_ai_added = max(0, d["totalLinesAdded"] - ai_added)
        non_ai_deleted = max(0, d["totalLinesDeleted"] - ai_deleted)

        result.append({
            "date": d["date"],
            "totalLinesAdded": d["totalLinesAdded"],
            "totalLinesDeleted": d["totalLinesDeleted"],
            "aiLinesAdded": ai_added,
            "aiLinesDeleted": ai_deleted,
            "nonAiLinesAdded": non_ai_added,
            "nonAiLinesDeleted": non_ai_deleted,
            "totalTabsShown": d["totalTabsShown"],
            "totalTabsAccepted": d["totalTabsAccepted"],
            "totalApplies": d["totalApplies"],
            "totalAccepts": d["totalAccepts"],
            "composerRequests": d["composerRequests"],
            "chatRequests": d["chatRequests"],
            "agentRequests": d["agentRequests"],
            "uniqueUsers": len(d["_activeUsers"]),
        })
    return result


def aggregate_leaderboard(rows):
    """Aggregate per-user rows into a leaderboard sorted by AI lines."""
    users = {}
    for r in rows:
        email = r.get("email", "")
        if not email:
            continue
        if email not in users:
            users[email] = {
                "email": email,
                "totalLinesAdded": 0,
                "totalLinesDeleted": 0,
                "aiLinesAdded": 0,
                "aiLinesDeleted": 0,
                "totalTabsAccepted": 0,
                "totalTabsShown": 0,
                "totalApplies": 0,
                "totalAccepts": 0,
                "agentRequests": 0,
                "chatRequests": 0,
                "activeDays": 0,
                "favoriteModel": {},
            }
        u = users[email]
        for f in ["totalLinesAdded", "totalLinesDeleted", "totalTabsShown",
                   "totalTabsAccepted", "totalApplies", "totalAccepts",
                   "agentRequests", "chatRequests"]:
            u[f] += r.get(f, 0)
        u["aiLinesAdded"] += r.get("acceptedLinesAdded", 0)
        u["aiLinesDeleted"] += r.get("acceptedLinesDeleted", 0)
        if r.get("isActive") or r.get("totalLinesAdded", 0) > 0:
            u["activeDays"] += 1
        model = r.get("mostUsedModel", "")
        if model and model != "default":
            u["favoriteModel"][model] = u["favoriteModel"].get(model, 0) + 1

    result = []
    for u in users.values():
        total = u["totalLinesAdded"] + u["totalLinesDeleted"]
        ai = u["aiLinesAdded"] + u["aiLinesDeleted"]
        fav_models = u.pop("favoriteModel")
        fav = max(fav_models, key=fav_models.get) if fav_models else ""
        name = u["email"].split("@")[0].replace(".", " ").title()
        u["name"] = name
        u["aiShare"] = round(ai / total * 100, 1) if total > 0 else 0
        u["favoriteModel"] = fav
        if u["activeDays"] > 0:
            result.append(u)

    result.sort(key=lambda x: x["aiLinesAdded"] + x["aiLinesDeleted"], reverse=True)
    for i, u in enumerate(result):
        u["rank"] = i + 1
    return result


def aggregate_user_monthly(rows):
    """Aggregate raw rows into per-user monthly buckets."""
    buckets = {}
    for r in rows:
        email = r.get("email", "")
        if not email:
            continue
        day = r.get("day", "")
        if len(day) < 7:
            continue
        month = day[:7]  # "YYYY-MM"
        key = (email, month)
        if key not in buckets:
            buckets[key] = {
                "totalLinesAdded": 0, "totalLinesDeleted": 0,
                "aiLinesAdded": 0, "aiLinesDeleted": 0,
                "agentRequests": 0, "chatRequests": 0,
            }
        b = buckets[key]
        b["totalLinesAdded"] += r.get("totalLinesAdded", 0)
        b["totalLinesDeleted"] += r.get("totalLinesDeleted", 0)
        b["aiLinesAdded"] += r.get("acceptedLinesAdded", 0)
        b["aiLinesDeleted"] += r.get("acceptedLinesDeleted", 0)
        b["agentRequests"] += r.get("agentRequests", 0)
        b["chatRequests"] += r.get("chatRequests", 0)

    result = {}
    for (email, month), b in sorted(buckets.items()):
        name = email.split("@")[0].replace(".", " ").title()
        if name not in result:
            result[name] = []
        total = b["totalLinesAdded"] + b["totalLinesDeleted"]
        ai = b["aiLinesAdded"] + b["aiLinesDeleted"]
        result[name].append({
            "month": month,
            "totalLines": total,
            "aiLines": ai,
            "manualLines": total - ai,
            "aiShare": round(ai / total * 100, 1) if total > 0 else 0,
            "agentRequests": b["agentRequests"],
            "chatRequests": b["chatRequests"],
        })
    return result


def prepare_raw_daily(rows):
    """Prepare compact per-user daily rows for frontend aggregation."""
    result = []
    for r in rows:
        email = r.get("email", "")
        if not email:
            continue
        result.append({
            "e": email,
            "d": r.get("day", ""),
            "la": r.get("totalLinesAdded", 0),
            "ld": r.get("totalLinesDeleted", 0),
            "aa": r.get("acceptedLinesAdded", 0),
            "ad": r.get("acceptedLinesDeleted", 0),
            "ar": r.get("agentRequests", 0),
            "cr": r.get("chatRequests", 0),
            "ta": r.get("totalTabsAccepted", 0),
            "ts": r.get("totalTabsShown", 0),
            "ap": r.get("totalApplies", 0),
            "ac": r.get("totalAccepts", 0),
            "x": 1 if (r.get("isActive") or r.get("totalLinesAdded", 0) > 0) else 0,
            "m": r.get("mostUsedModel", ""),
        })
    return result


def write_data_js(raw_daily, output_path):
    """Write cursor_usage.js with compact raw daily rows for frontend aggregation."""
    with open(output_path, "w") as f:
        f.write("const R=")
        json.dump(raw_daily, f, separators=(",", ":"))
        f.write(";\n")



def main():
    start = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START
    end = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_END

    api_key = load_api_key()
    print(f"Cursor Analytics Fetcher")
    print(f"  Period: {start} → {end}")
    print(f"  API: {API_BASE}/teams/daily-usage-data (Admin API, Basic Auth)")
    print()

    print("Fetching team members...")
    members = api_get("/teams/members", api_key)
    team_size = len(members.get("teamMembers", []))
    print(f"  Team size: {team_size} members\n")

    print("Fetching daily usage data...")
    raw_rows = fetch_daily_usage(api_key, start, end)
    print(f"  Total raw rows: {len(raw_rows)}\n")

    print("Preparing raw daily data...")
    raw_daily = prepare_raw_daily(raw_rows)
    print(f"  Rows for frontend: {len(raw_daily)}\n")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    js_path = os.path.join(data_dir, "cursor_usage.js")

    write_data_js(raw_daily, js_path)
    print(f"Wrote {js_path}")

    daily_data = aggregate_daily(raw_rows)
    total_added = sum(d["totalLinesAdded"] for d in daily_data)
    total_ai = sum(d["aiLinesAdded"] for d in daily_data)
    ai_pct = (total_ai / total_added * 100) if total_added > 0 else 0
    print(f"\nSummary:")
    print(f"  AI Share: {ai_pct:.1f}%")
    print(f"  Total Lines Added: {total_added:,}")
    print(f"  AI Lines Added: {total_ai:,}")
    print(f"  Users: {len(set(r['e'] for r in raw_daily))}")
    print(f"  Days: {len(daily_data)}")


if __name__ == "__main__":
    main()
