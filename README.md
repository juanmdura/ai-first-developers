# AI-First Developers Dashboard

A single-page analytics dashboard that visualizes Cursor AI usage across the engineering team. Built to track AI adoption, identify power users, and monitor coding trends over time.

## What it shows

**Lines of Code: AI vs Manual** — Total lines modified with breakdowns by source (AI / Manual), a stacked distribution bar, and a daily time-series with AI share trend.

**AI-First Developers** — Active user count, average/median AI share across the team, top contributor, tab accept rate, an active users chart with trend line, and a full leaderboard with per-developer stats.

**AI Usage** — Daily AI requests (Agent + Chat) with trend line, and an Added vs Deleted breakdown by operation.

## Setup

1. Copy the environment template and add your Cursor Admin API key:

```bash
cp .env.example .env
# Edit .env and set CURSOR_API_TOKEN
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Fetch data from the Cursor API:

```bash
python fetch_data.py
```

This generates `data.js` consumed by the dashboard.

4. Open the dashboard:

```bash
python -m http.server 8080
# Visit http://localhost:8080
```

## Project structure

```
├── index.html          # Dashboard UI (HTML + CSS + Chart.js)
├── data.js             # Generated data consumed by the dashboard
├── fetch_data.py       # Fetches data from Cursor Admin API
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── .gitignore
```

## Data source

Data is fetched from the [Cursor Admin API](https://docs.cursor.com/account/api-keys) endpoint `/teams/daily-usage-data` using Basic Authentication. The script handles the 30-day window limit by paginating across the full date range automatically.

## Tech stack

- **Frontend**: Vanilla HTML/CSS/JS, [Chart.js](https://www.chartjs.org/), [Inter](https://rsms.me/inter/) font
- **Data**: Python + [requests](https://docs.python-requests.org/)
- **Branding**: [Zubale](https://zubale.com/) design system colors
