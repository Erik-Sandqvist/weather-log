"""Daily weather log for Stockholm, based on SMHI open data.

Downloads hourly observations from SMHI (free, no API key), turns them into one
row per calendar day in data/weather.csv and regenerates README.md.
Missing days within the last BACKFILL_DAYS are filled in automatically, so a
skipped run does not leave a gap.

Data source: SMHI (Swedish Meteorological and Hydrological Institute),
licensed under CC BY 4.0.
Uses only the Python standard library.
"""

import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "weather.csv"
README_PATH = ROOT / "README.md"

TZ = ZoneInfo("Europe/Stockholm")
BACKFILL_DAYS = 14
SHOW_DAYS = 14
MIN_HOURS = 18  # a day needs at least this many hourly readings to be logged

API = "https://opendata-download-metobs.smhi.se/api/version/1.0"
TEMP_STATION = ("98230", "Stockholm-Observatoriekullen A")
WIND_STATION = ("97200", "Stockholm-Bromma Flygplats")
PARAM_TEMP = "1"    # air temperature, hourly instantaneous value (°C)
PARAM_PRECIP = "7"  # precipitation, hourly sum (mm)
PARAM_WIND = "4"    # wind speed, hourly 10-minute mean (m/s)

FIELDS = ["date", "temp_max", "temp_min", "temp_mean", "precipitation_mm", "wind_max_ms"]


def fetch(param: str, station: str, retries: int = 3) -> list[dict] | None:
    url = f"{API}/parameter/{param}/station/{station}/period/latest-months/data.json"
    req = urllib.request.Request(url, headers={"User-Agent": "weather-log (github.com/Erik-Sandqvist/weather-log)"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp).get("value") or []
        except Exception as exc:  # noqa: BLE001 - log and retry on any failure
            print(f"SMHI param {param} station {station}, attempt {attempt} failed: {exc}", file=sys.stderr)
            time.sleep(2 * attempt)
    return None


def by_day(values: list[dict] | None, shift_hours: int = 0) -> dict[date, list[float]]:
    """Group hourly readings by local calendar day.

    shift_hours moves each timestamp back before grouping. Hourly sums are
    stamped at the end of their hour, so precipitation uses shift_hours=1.
    """
    days: dict[date, list[float]] = defaultdict(list)
    for v in values or []:
        if v.get("quality") not in ("G", "Y") or v.get("value") in (None, ""):
            continue
        ts = datetime.fromtimestamp(v["date"] / 1000, timezone.utc) - timedelta(hours=shift_hours)
        days[ts.astimezone(TZ).date()].append(float(v["value"]))
    return days


def summarize(day: date, temp, precip, wind) -> dict | None:
    t = temp.get(day, [])
    if len(t) < MIN_HOURS:
        return None
    p = precip.get(day, [])
    w = wind.get(day, [])
    return {
        "date": day.isoformat(),
        "temp_max": round(max(t), 1),
        "temp_min": round(min(t), 1),
        "temp_mean": round(sum(t) / len(t), 1),
        "precipitation_mm": round(sum(p), 1) if len(p) >= MIN_HOURS else "",
        "wind_max_ms": round(max(w), 1) if len(w) >= MIN_HOURS else "",
    }


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


def num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value) -> str:
    return "–" if num(value) is None else str(value)


def render_readme(rows: list[dict], updated: str) -> str:
    recent = rows[-SHOW_DAYS:][::-1]
    lines = [
        "# 🌦️ Daily weather log – Stockholm",
        "",
        "An automated log of yesterday's weather in Stockholm, built from "
        "[SMHI open data](https://www.smhi.se/data/meteorologi/ladda-ner-meteorologiska-observationer) "
        "and committed to this repo every morning.",
        "",
        f"**Days logged:** {len(rows)}  ",
        f"**Last updated:** {updated}",
        "",
        f"## Last {len(recent)} days",
        "",
        "| Date | Max °C | Min °C | Mean °C | Precipitation (mm) | Max wind (m/s) |",
        "|------|-------:|-------:|--------:|-------------------:|---------------:|",
    ]
    for r in recent:
        lines.append(
            f"| {r['date']} | {fmt(r['temp_max'])} | {fmt(r['temp_min'])} | {fmt(r['temp_mean'])} "
            f"| {fmt(r['precipitation_mm'])} | {fmt(r['wind_max_ms'])} |"
        )
    if not recent:
        lines.append("| – | – | – | – | – | – |")

    with_max = [r for r in rows if num(r["temp_max"]) is not None]
    with_min = [r for r in rows if num(r["temp_min"]) is not None]
    with_rain = [r for r in rows if num(r["precipitation_mm"]) is not None]
    if with_max and with_min:
        warmest = max(with_max, key=lambda r: num(r["temp_max"]))
        coldest = min(with_min, key=lambda r: num(r["temp_min"]))
        lines += [
            "",
            "## All-time records",
            "",
            f"- 🔥 Warmest: **{warmest['temp_max']} °C** ({warmest['date']})",
            f"- 🧊 Coldest: **{coldest['temp_min']} °C** ({coldest['date']})",
        ]
        if with_rain:
            wettest = max(with_rain, key=lambda r: num(r["precipitation_mm"]))
            lines.append(f"- 🌧️ Wettest: **{wettest['precipitation_mm']} mm** ({wettest['date']})")

    lines += [
        "",
        "Full history: [`data/weather.csv`](data/weather.csv)",
        "",
        "---",
        "",
        f"Source: [SMHI](https://www.smhi.se/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). "
        f"Temperature and precipitation from {TEMP_STATION[1]}, wind from {WIND_STATION[1]}.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rows = load_rows()
    have = {r["date"] for r in rows}

    temp_raw = fetch(PARAM_TEMP, TEMP_STATION[0])
    if temp_raw is None:
        print("Could not reach SMHI; updating timestamp only.", file=sys.stderr)
    else:
        temp = by_day(temp_raw)
        precip = by_day(fetch(PARAM_PRECIP, TEMP_STATION[0]), shift_hours=1)
        wind = by_day(fetch(PARAM_WIND, WIND_STATION[0]))

        yesterday = datetime.now(TZ).date() - timedelta(days=1)
        added = []
        for offset in range(BACKFILL_DAYS - 1, -1, -1):
            day = yesterday - timedelta(days=offset)
            if day.isoformat() in have:
                continue
            row = summarize(day, temp, precip, wind)
            if row:
                rows.append(row)
                added.append(row["date"])
        if added:
            rows.sort(key=lambda r: r["date"])
            save_rows(rows)
            print(f"Logged {len(added)} day(s): {', '.join(added)}")
        else:
            print("No new complete days to log.")

    updated = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")
    README_PATH.write_text(render_readme(rows, updated), encoding="utf-8")


if __name__ == "__main__":
    main()

# Detta funkar inte
# varför inte?    