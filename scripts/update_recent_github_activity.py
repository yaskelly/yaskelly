from __future__ import annotations

import html
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "yaskelly"
OUT = Path("assets/recent-github-activity.svg")


def fetch_events():
    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "yaskelly-profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def ago(ts: str) -> str:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    seconds = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def describe(e):
    typ = e.get("type", "")
    repo = e.get("repo", {}).get("name", "GitHub")
    p = e.get("payload", {})
    if typ == "PushEvent":
        ref = p.get("ref", "").replace("refs/heads/", "")
        return "⬆️", f"Pushed to {repo}", ref or "Public contribution"
    if typ == "PullRequestEvent":
        action = p.get("action", "updated").capitalize()
        num = p.get("number", "")
        return "🔀", f"{action} PR in {repo}", f"Pull request #{num}" if num else "Pull request"
    if typ == "IssuesEvent":
        action = p.get("action", "updated").capitalize()
        issue = p.get("issue", {}).get("number", "")
        return "📝", f"{action} issue in {repo}", f"Issue #{issue}" if issue else "Issue"
    if typ == "IssueCommentEvent":
        issue = p.get("issue", {}).get("number", "")
        return "💬", f"Commented on issue in {repo}", f"Issue #{issue}" if issue else "Discussion"
    if typ == "WatchEvent":
        return "⭐", f"Starred {repo}", "Public GitHub engagement"
    if typ == "CreateEvent":
        ref_type = p.get("ref_type", "repository")
        return "✨", f"Created {ref_type} in {repo}", p.get("ref") or "Public GitHub activity"
    if typ == "ForkEvent":
        return "🍴", f"Forked {repo}", "Open-source activity"
    return "📌", f"{typ.replace('Event', '')} in {repo}", "Public GitHub activity"


def pick(events):
    chosen = []
    seen = set()
    for e in events:
        icon, title, detail = describe(e)
        key = (e.get("type"), e.get("repo", {}).get("name"), title)
        if key in seen:
            continue
        seen.add(key)
        chosen.append((icon, title, detail, ago(e.get("created_at", ""))))
        if len(chosen) == 4:
            break
    while len(chosen) < 4:
        chosen.append(("📌", "Public GitHub activity", "Updates automatically", ""))
    return chosen


def esc(s):
    return html.escape(str(s), quote=True)


def render(items):
    rows = []
    ys = [103, 171, 239, 307]
    for i, ((icon, title, detail, when), y) in enumerate(zip(items, ys)):
        rows.append(f'<text x="30" y="{y}" font-size="22">{esc(icon)}</text>')
        rows.append(f'<text x="68" y="{y-4}" class="h">{esc(title[:43])}</text>')
        rows.append(f'<text x="68" y="{y+17}" class="s">{esc(detail[:46])}</text>')
        if when:
            rows.append(f'<text x="468" y="{y-4}" text-anchor="end" class="s">{esc(when)}</text>')
        if i < 3:
            rows.append(f'<line x1="28" y1="{y+33}" x2="472" y2="{y+33}" class="sep"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="390" viewBox="0 0 500 390"><style>.t{{font:700 25px Arial,sans-serif;fill:#1f2328}}.h{{font:700 16px Arial,sans-serif;fill:#1f2328}}.s{{font:14px Arial,sans-serif;fill:#57606a}}.cta{{font:700 16px Arial,sans-serif;fill:#ff2f78}}.line{{stroke:#ff7fa8;stroke-width:2}}.sep{{stroke:#ffd0df;stroke-width:1}}</style><rect x="2" y="2" width="496" height="386" rx="18" fill="#fff0f5" stroke="#ff9fbd" stroke-width="1.5"/><text x="28" y="46" class="t">📱  Recent GitHub Activity</text><line x1="28" y1="62" x2="472" y2="62" class="line"/>{''.join(rows)}<line x1="28" y1="342" x2="472" y2="342" class="sep"/><text x="250" y="371" text-anchor="middle" class="cta">View more on GitHub →</text></svg>'''


if __name__ == "__main__":
    OUT.write_text(render(pick(fetch_events())), encoding="utf-8")
