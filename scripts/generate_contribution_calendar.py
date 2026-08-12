#!/usr/bin/env python3
"""Generate a pink GitHub contribution calendar SVG from GitHub's official GraphQL data."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
import urllib.request
from pathlib import Path

USERNAME = os.getenv("GITHUB_PROFILE_USERNAME", "yaskelly")
TOKEN = os.getenv("GITHUB_TOKEN")
OUTPUT = Path(os.getenv("CONTRIBUTION_SVG", "assets/contribution-activity.svg"))

COLORS = [
    "#FFF1F5",  # no activity
    "#FFD6E3",  # level 1
    "#FFABC3",  # level 2
    "#FF6B9A",  # level 3
    "#D81B60",  # level 4
]
BORDER = "#FFB3C9"
TEXT = "#24292F"
ACCENT = "#FF2F78"
MUTED = "#57606A"


def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required")

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "yaskelly-profile-contribution-calendar",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)

    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def percentile_nearest_rank(values: list[int], percentile: float) -> int:
    """Nearest-rank percentile for a non-empty sorted list."""
    if not values:
        return 0
    rank = max(1, int((percentile * len(values) + 0.9999999999)))
    return values[min(rank - 1, len(values) - 1)]


def level_for(count: int, q1: int, q2: int, q3: int) -> int:
    if count <= 0:
        return 0
    if count <= q1:
        return 1
    if count <= q2:
        return 2
    if count <= q3:
        return 3
    return 4


def label_ranges(q1: int, q2: int, q3: int, maximum: int) -> list[str]:
    def rng(lo: int, hi: int) -> str:
        if hi < lo:
            return "—"
        return str(lo) if lo == hi else f"{lo}–{hi}"

    return [
        "0",
        rng(1, q1),
        rng(q1 + 1, q2),
        rng(q2 + 1, q3),
        f"{q3 + 1}+" if maximum > q3 else "—",
    ]


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def build_svg(calendar: dict, restricted_count: int) -> str:
    weeks = calendar["weeks"]
    days = [day for week in weeks for day in week["contributionDays"]]
    active_counts = sorted(day["contributionCount"] for day in days if day["contributionCount"] > 0)

    q1 = percentile_nearest_rank(active_counts, 0.25)
    q2 = percentile_nearest_rank(active_counts, 0.50)
    q3 = percentile_nearest_rank(active_counts, 0.75)
    maximum = max(active_counts, default=0)
    ranges = label_ranges(q1, q2, q3, maximum)

    cell = 13
    gap = 4
    step = cell + gap
    grid_x = 72
    grid_y = 74
    width = max(900, grid_x + len(weeks) * step + 32)
    height = 265

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(USERNAME)} GitHub Contribution Activity — Last 365 Days</title>',
        '<desc id="desc">Contribution calendar generated from GitHub contributionCount values. Pink intensity represents quartiles of active contribution days, not hours worked.</desc>',
        '<style>',
        f'text {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; fill:{TEXT}; }}',
        '.small { font-size: 11px; } .month { font-size: 11px; } .title { font-size: 17px; font-weight: 700; }',
        f'.muted {{ fill:{MUTED}; }} .accent {{ fill:{ACCENT}; }}',
        '</style>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="#FFFFFF" stroke="{BORDER}"/>',
        f'<text x="22" y="32" class="title accent">Contribution Activity</text>',
        '<text x="188" y="32" class="small muted">(Last 365 Days)</text>',
    ]

    last_month = None
    for wi, week in enumerate(weeks):
        first_day = week["contributionDays"][0]
        month = dt.date.fromisoformat(first_day["date"]).strftime("%b")
        if month != last_month:
            x = grid_x + wi * step
            parts.append(f'<text x="{x}" y="57" class="month">{escape(month)}</text>')
            last_month = month

    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = grid_y + row * step + 11
        parts.append(f'<text x="24" y="{y}" class="small">{label}</text>')

    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            weekday = dt.date.fromisoformat(day["date"]).weekday()
            row = (weekday + 1) % 7
            count = day["contributionCount"]
            level = level_for(count, q1, q2, q3)
            x = grid_x + wi * step
            y = grid_y + row * step
            tooltip = f'{day["date"]}: {count} contribution' + ("" if count == 1 else "s") + f' · Level {level}'
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{COLORS[level]}" stroke="#FFFFFF" stroke-width="0.5">'
                f'<title>{escape(tooltip)}</title></rect>'
            )

    legend_y = 211
    parts.append(f'<text x="22" y="{legend_y}" class="small muted">Activity levels (contributions/day)</text>')
    legend_x = 225
    for idx, (color, label) in enumerate(zip(COLORS, ranges)):
        x = legend_x + idx * 105
        parts.append(f'<rect x="{x}" y="{legend_y-11}" width="12" height="12" rx="2" fill="{color}"/>')
        parts.append(f'<text x="{x+18}" y="{legend_y}" class="small">{escape(label)}</text>')

    total = calendar["totalContributions"]
    active_days = len(active_counts)
    footer = f'{total} public/visible contributions · {active_days} active days · Q1≤{q1} · Q2≤{q2} · Q3≤{q3}'
    parts.append(f'<text x="22" y="239" class="small muted">{escape(footer)}</text>')
    if restricted_count:
        parts.append(f'<text x="22" y="256" class="small muted">GitHub also reports {restricted_count} restricted contribution(s).</text>')
    else:
        parts.append('<text x="22" y="256" class="small muted">Color intensity represents GitHub activity counts, not time or hours worked.</text>')

    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    from_dt = f"{start.isoformat()}T00:00:00Z"
    to_dt = f"{today.isoformat()}T23:59:59Z"

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
              }
            }
          }
        }
      }
    }
    """

    data = graphql(query, {"login": USERNAME, "from": from_dt, "to": to_dt})
    user = data.get("user")
    if not user:
        raise RuntimeError(f"GitHub user not found: {USERNAME}")

    collection = user["contributionsCollection"]
    svg = build_svg(collection["contributionCalendar"], collection["restrictedContributionsCount"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Generated {OUTPUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
