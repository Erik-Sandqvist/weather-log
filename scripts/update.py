"""Daily weather log for Stockholm.

Fetches yesterday's weather from Open-Meteo (free, no API key), appends it to
data/weather.csv and regenerates README.md with the latest days.
Uses only the Python standard library.
"""

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "weather.csv"
README_PATH = ROOT / "README.md"

CITY = os.environ.get("CITY", "Stockholm")
LAT = os.environ.get("LAT", "59.33")
LON = os.environ.get("LON", "18.07")
TZ = os.environ.get("TZ_NAME", "Europe/Stockholm")
SHOW_DAYS = 14

FIELDS = ["date", "temp_max", "temp_min", "precipitation_mm", "wind_max_kmh"]

API_URL = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
    f"&timezone={TZ.replace('/', '%2F')}"
    "&past_days=1&forecast_days=1"
)


def fetch_yesterday(retries: int = 3) -> dict | None:
    """Return yesterday's complete weather row, or None if the API is unreachable."""
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(API_URL, timeout=20) as resp:
                daily = json.load(resp)["daily"]
            # past_days=1 -> index 0 is yesterday (a complete day), index 1 is today.
            return {
                "date": daily["time"][0],
                "temp_max": daily["temperature_2m_max"][0],
                "temp_min": daily["temperature_2m_min"][0],
                "precipitation_mm": daily["precipitation_sum"][0],
                "wind_max_kmh": daily["wind_speed_10m_max"][0],
            }
        except Exception as exc:  # noqa: BLE001 - log and retry on any failure
            print(f"Attempt {attempt} failed: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    return None


def load_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value) -> str:
    return "–" if value in (None, "", "None") else str(value)


def render_readme(rows: list[dict], updated: str) -> str:
    recent = rows[-SHOW_DAYS:][::-1]
    lines = [
        f"# 🌦️ Daily weather log – {CITY}",
        "",
        "An automated log that fetches yesterday's weather every morning via "
        "[Open-Meteo](https://open-meteo.com/) and commits it to this repo using GitHub Actions.",
        "",
        f"**Days logged:** {len(rows)}  ",
        f"**Last updated:** {updated}",
        "",
        f"## Last {min(SHOW_DAYS, len(rows))} days",
        "",
        "| Date | Max °C | Min °C | Precipitation (mm) | Max wind (km/h) |",
        "|------|-------:|-------:|-------------------:|----------------:|",
    ]
    for r in recent:
        lines.append(
            f"| {r['date']} | {fmt(r['temp_max'])} | {fmt(r['temp_min'])} "
            f"| {fmt(r['precipitation_mm'])} | {fmt(r['wind_max_kmh'])} |"
        )
    if not recent:
        lines.append("| – | – | – | – | – |")

    temps = [float(r["temp_max"]) for r in rows if r["temp_max"] not in ("", "None")]
    if temps:
        warmest = max(rows, key=lambda r: float(r["temp_max"]) if r["temp_max"] not in ("", "None") else -999)
        coldest = min(rows, key=lambda r: float(r["temp_min"]) if r["temp_min"] not in ("", "None") else 999)
        lines += [
            "",
            "## All-time records",
            "",
            f"- 🔥 Warmest day: **{warmest['temp_max']} °C** ({warmest['date']})",
            f"- 🧊 Coldest night: **{coldest['temp_min']} °C** ({coldest['date']})",
        ]

    lines += [
        "",
        "Full history: [`data/weather.csv`](data/weather.csv)",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rows = load_rows()
    new = fetch_yesterday()
    if new:
        rows = [r for r in rows if r["date"] != new["date"]] + [new]
        rows.sort(key=lambda r: r["date"])
        save_rows(rows)
        print(f"Logged {new['date']}: {new}")
    else:
        print("Could not fetch weather data; updating timestamp only.", file=sys.stderr)

    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    README_PATH.write_text(render_readme(rows, updated), encoding="utf-8")


if __name__ == "__main__":
    main()

# Detta funkar inte
# varför inte?    