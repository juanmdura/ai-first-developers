#!/usr/bin/env python3
"""
Dashboard server: serves static files and provides a /api/chat endpoint
that uses Google Gemini to generate insights about the analytics data.
"""

import json
import os
import sys

from flask import Flask, request, jsonify, send_from_directory
from google import genai

script_dir = os.path.dirname(os.path.abspath(__file__))

# Load .env
env_path = os.path.join(script_dir, ".env")
if os.path.exists(env_path):
    for line in open(env_path):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY not found in environment or .env", file=sys.stderr)
    sys.exit(1)

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = """You are an AI analytics assistant embedded in a Cursor AI usage dashboard for Zubale's engineering team.
You help users understand their team's AI coding adoption metrics.

The dashboard tracks: lines of code (AI-generated vs manual), active users, AI share per developer,
tab accept rates, agent/chat requests, and monthly trends.

When the user asks a question, you receive a JSON summary of the currently displayed (possibly filtered) data.
Use it to provide specific, data-driven insights. Be concise and use numbers.
Format responses in markdown. Use bullet points for lists. Bold key metrics."""

app = Flask(__name__, static_folder=script_dir)


@app.route("/")
def index():
    return send_from_directory(script_dir, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(script_dir, path)


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()
    data_summary = body.get("context", "")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    prompt = f"""{SYSTEM_PROMPT}

## Current Dashboard Data
```json
{data_summary}
```

## User Question
{question}"""

    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        return jsonify({"answer": response.text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Dashboard server running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
