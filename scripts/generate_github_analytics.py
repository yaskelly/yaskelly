#!/usr/bin/env python3
"""Generate custom pink GitHub analytics SVG cards for the profile README."""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path

USERNAME = os.getenv("GITHUB_PROFILE_USERNAME", "yaskelly")
TOKEN = os.getenv("GITHUB_TOKEN")
ASSETS = Path("assets")

PINK = "#FF2F78"
PINK_DARK = "#D81B60"
PINK_MED = "#FF6B9A"
PINK_LIGHT = "#FFD6E3"
PINK_PALE = "#FFF1F5"
BORDER = "#FFB3C9"
TEXT = "#24292F"
MUTED = "#57606A"
WHITE = "#FFFFFF"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def graphql(query: str, variables: dict) -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "yaskelly-profile-analytics",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}K".replace(".0K", "K")
    return str(n)


def svg_shell(title: str) -> list[str]:
    width, height = 390, 270
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;fill:#24292F}.title{font-size:17px;font-weight:700}.label{font-size:12px}.value{font-size:13px;font-weight:700}.muted{fill:#57606A}.pink{fill:#FF2F78}</style>',
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="{WHITE}" stroke="{BORDER}"/>',
        f'<text x="18" y="30" class="title pink">{esc(title)}</text>',
    ]


def fetch_profile_data() -> dict:
    today = dt.datetime.now(dt.timezone.utc).date()
    start = today - dt.timedelta(days=364)
    query = """
    query($login:String!,$from:DateTime!,$to:DateTime!,$cursor:String) {
      user(login:$login) {
        followers { totalCount }
        repositories(first:100, after:$cursor, ownerAffiliations:OWNER, privacy:PUBLIC, orderBy:{field:UPDATED_AT,direction:DESC}) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { stargazerCount isFork }
        }
        contributionsCollection(from:$from,to:$to) {
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          restrictedContributionsCount
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z",
        "cursor": None,
    }
    first = graphql(query, variables)["user"]
    repos = list(first["repositories"]["nodes"])
    page = first["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        variables["cursor"] = page["endCursor"]
        nxt = graphql(query, variables)["user"]["repositories"]
        repos.extend(nxt["nodes"])
        page = nxt["pageInfo"]
    first["repositories"]["nodes"] = repos
    return first


def fetch_language_repositories() -> list[dict]:
    """Owned or explicitly collaborated repositories, public or private, excluding forks later."""
    query = """
    query($login:String!,$cursor:String) {
      user(login:$login) {
        repositories(
          first:100,
          after:$cursor,
          ownerAffiliations:[OWNER,COLLABORATOR],
          orderBy:{field:UPDATED_AT,direction:DESC}
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            nameWithOwner
            isFork
            isPrivate
            languages(first:12, orderBy:{field:SIZE,direction:DESC}) {
              edges { size node { name } }
            }
          }
        }
      }
    }
    """
    cursor = None
    repos: list[dict] = []
    while True:
        conn = graphql(query, {"login": USERNAME, "cursor": cursor})["user"]["repositories"]
        repos.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return repos


def compute_streaks(days: list[dict]) -> tuple[int, int]:
    ordered = sorted(days, key=lambda d: d["date"])
    longest = running = 0
    for d in ordered:
        if d["contributionCount"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0
    current = 0
    started = False
    for d in reversed(ordered):
        if d["contributionCount"] > 0:
            current += 1
            started = True
        elif started:
            break
    return current, longest


def stats_card(data: dict) -> str:
    repos = data["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos if not r["isFork"])
    c = data["contributionsCollection"]
    rows = [
        ("★", "Total Stars Earned", stars),
        ("▣", "Public Repositories", data["repositories"]["totalCount"]),
        ("●", "Commits (365d)", c["totalCommitContributions"]),
        ("⑂", "Pull Requests (365d)", c["totalPullRequestContributions"]),
        ("○", "Issues (365d)", c["totalIssueContributions"]),
        ("♙", "Followers", data["followers"]["totalCount"]),
    ]
    parts = svg_shell("GitHub Stats")
    y = 64
    for icon, label, value in rows:
        parts.append(f'<text x="20" y="{y}" class="label pink">{esc(icon)}</text>')
        parts.append(f'<text x="43" y="{y}" class="label">{esc(label)}</text>')
        parts.append(f'<text x="244" y="{y}" class="value">{esc(fmt(value))}</text>')
        y += 31
    parts += [
        f'<circle cx="322" cy="145" r="42" fill="none" stroke="{PINK_LIGHT}" stroke-width="14"/>',
        f'<circle cx="322" cy="145" r="42" fill="none" stroke="{PINK}" stroke-width="14" stroke-dasharray="190 74" transform="rotate(-90 322 145)"/>',
        f'<text x="322" y="142" text-anchor="middle" style="font-size:23px;font-weight:700">{esc(fmt(c["totalCommitContributions"]))}</text>',
        '<text x="322" y="162" text-anchor="middle" class="label muted">commits / 365d</text>',
        '</svg>'
    ]
    return "\n".join(parts) + "\n"


def languages_card(repos: list[dict]) -> str:
    totals: dict[str, int] = defaultdict(int)
    analyzed = 0
    private_count = 0
    for repo in repos:
        if repo["isFork"]:
            continue
        analyzed += 1
        if repo["isPrivate"]:
            private_count += 1
        for edge in repo["languages"]["edges"]:
            totals[edge["node"]["name"]] += edge["size"]

    grand = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    parts = svg_shell("Most Used Languages")
    y = 62
    for name, value in top:
        pct = value / grand * 100
        bar = max(4, int(150 * pct / 100))
        parts.append(f'<text x="20" y="{y}" class="label">{esc(name)}</text>')
        parts.append(f'<rect x="137" y="{y-10}" width="150" height="9" rx="4.5" fill="{PINK_PALE}"/>')
        parts.append(f'<rect x="137" y="{y-10}" width="{bar}" height="9" rx="4.5" fill="{PINK}"/>')
        parts.append(f'<text x="305" y="{y}" class="value">{pct:.1f}%</text>')
        y += 30
    parts.append(f'<text x="20" y="250" class="muted" style="font-size:10px">{analyzed} owned/collaborated repos analyzed · {private_count} private</text>')
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


def streak_card(data: dict) -> str:
    c = data["contributionsCollection"]
    days = [d for w in c["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    current, longest = compute_streaks(days)
    total = c["contributionCalendar"]["totalContributions"] + c["restrictedContributionsCount"]
    parts = svg_shell("Streak Stats")
    parts += [
        f'<circle cx="84" cy="118" r="42" fill="none" stroke="{PINK_LIGHT}" stroke-width="14"/>',
        f'<circle cx="84" cy="118" r="42" fill="none" stroke="{PINK}" stroke-width="14" stroke-dasharray="190 74" transform="rotate(-90 84 118)"/>',
        '<text x="84" y="126" text-anchor="middle" style="font-size:28px">🔥</text>',
        f'<text x="205" y="91" class="value" style="font-size:29px">{current}</text>',
        '<text x="205" y="113" class="label muted">Current Streak</text>',
        f'<text x="40" y="194" class="value" style="font-size:25px">{longest}</text>',
        '<text x="107" y="194" class="label muted">Longest Streak</text>',
        f'<text x="40" y="232" class="value" style="font-size:25px">{fmt(total)}</text>',
        '<text x="120" y="232" class="label muted">Total Contributions*</text>',
        '<text x="20" y="254" class="muted" style="font-size:9px">*Total includes restricted contributions; streaks use dated visible activity.</text>',
        '</svg>'
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    profile = fetch_profile_data()
    language_repos = fetch_language_repositories()
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "github-stats.svg").write_text(stats_card(profile), encoding="utf-8")
    (ASSETS / "top-languages.svg").write_text(languages_card(language_repos), encoding="utf-8")
    (ASSETS / "streak-stats.svg").write_text(streak_card(profile), encoding="utf-8")
    print(f"Generated GitHub analytics cards; language repositories available: {len(language_repos)}")


if __name__ == "__main__":
    main()
