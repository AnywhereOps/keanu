"""bridge.py - thin client to openpaw memory search."""

import json
import subprocess


def recall_via_openpaw(query, max_results=6, min_score=0.35):
    cmd = [
        "openclaw", "memory", "search", query,
        "--json",
        "--max-results", str(max_results),
        "--min-score", str(min_score),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        return data.get("results", [])
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def openpaw_available():
    try:
        result = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
