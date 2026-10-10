from __future__ import annotations
import base64, html, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
README = ROOT / "README.md"
CHANNEL = "https://www.youtube.com/@yaskcode"
UA = {"User-Agent": "Mozilla/5.0"}

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

page = get(CHANNEL).decode("utf-8", "ignore")
m = re.search(r'"channelId":"(UC[^"]+)"', page)
if not m:
    raise RuntimeError("Could not resolve YouTube channel ID")
channel_id = m.group(1)
feed = get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
root = ET.fromstring(feed)
ns = {"a":"http://www.w3.org/2005/Atom", "yt":"http://www.youtube.com/xml/schemas/2015"}
entries = root.findall("a:entry", ns)[:3]
if not entries:
    raise RuntimeError("No YouTube videos found")

links = []
for i, e in enumerate(entries, 1):
    vid = e.findtext("yt:videoId", namespaces=ns)
    title = e.findtext("a:title", namespaces=ns) or "YouTube video"
    published = e.findtext("a:published", namespaces=ns) or ""
    date = datetime.fromisoformat(published.replace("Z", "+00:00")).strftime("%d %b %Y") if published else ""
    thumb = get(f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg")
    b64 = base64.b64encode(thumb).decode()
    safe_title = html.escape(title)
    # Wrap title into at most 3 readable lines.
    words, lines, line = title.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if len(trial) > 39 and line:
            lines.append(line); line = w
        else:
            line = trial
    if line: lines.append(line)
    lines = lines[:3]
    if len(lines) == 3 and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(" .") + "…"
    tspans = "".join(f'<tspan x="22" dy="{0 if j == 0 else 27}">{html.escape(t)}</tspan>' for j,t in enumerate(lines))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="350" viewBox="0 0 500 350">
<rect x="2" y="2" width="496" height="346" rx="18" fill="#FFF1F5" stroke="#FFB3C9" stroke-width="2"/>
<clipPath id="c"><rect x="18" y="18" width="464" height="210" rx="12"/></clipPath>
<image x="18" y="18" width="464" height="210" preserveAspectRatio="xMidYMid slice" clip-path="url(#c)" href="data:image/jpeg;base64,{b64}"/>
<text x="22" y="260" font-family="Arial,Helvetica,sans-serif" font-size="21" font-weight="700" fill="#1f2328">{tspans}</text>
<text x="22" y="329" font-family="Arial,Helvetica,sans-serif" font-size="16" fill="#59636e">{date}</text>
</svg>'''
    (ASSETS / f"youtube-video-{i}.svg").write_text(svg, encoding="utf-8")
    links.append(f'<a href="https://www.youtube.com/watch?v={vid}"><img width="32%" src="assets/youtube-video-{i}.svg" alt="{safe_title}" /></a>')

text = README.read_text(encoding="utf-8")
start = "<!-- YOUTUBE:START -->"
end = "<!-- YOUTUBE:END -->"
block = start + '\n<p align="center">\n  ' + '\n  '.join(links) + '\n</p>\n' + end
if start in text and end in text:
    text = re.sub(re.escape(start) + r".*?" + re.escape(end), block, text, flags=re.S)
else:
    raise RuntimeError("YouTube markers missing from README")
README.write_text(text, encoding="utf-8")
