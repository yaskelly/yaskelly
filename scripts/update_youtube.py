from __future__ import annotations
import html
import re
import urllib.request
import urllib.error
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANNEL = "https://www.youtube.com/@yaskcode"
UA = {"User-Agent": "Mozilla/5.0"}
START = "<!-- YOUTUBE:START -->"
END = "<!-- YOUTUBE:END -->"

def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in (404, 429, 500, 502, 503, 504) or attempt == 3:
                raise
        except urllib.error.URLError:
            if attempt == 3:
                raise
        time.sleep(2 ** (attempt + 1))

def render(entries, ns, english=False):
    lines = []
    captions = []
    for entry in entries:
        video_id = entry.findtext("yt:videoId", namespaces=ns) or ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise RuntimeError("Invalid YouTube video ID")
        title = entry.findtext("a:title", namespaces=ns) or "YouTube video"
        published = entry.findtext("a:published", namespaces=ns) or ""
        date = datetime.fromisoformat(published.replace("Z", "+00:00")).date().isoformat() if published else ""
        safe_title = html.escape(title, quote=True)
        label = "Published" if english else "Publicado"
        lines.append(
            f'<a href="https://www.youtube.com/watch?v={video_id}" title="{safe_title}">'
            f'<img src="https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" width="32%" alt="{safe_title}" /></a>'
        )
        captions.append(f'- <a href="https://www.youtube.com/watch?v={video_id}">{safe_title}</a> · {date}')
    summary = "Video titles and dates" if english else "Títulos y fechas de los videos"
    return (START + '\n<p align="center">\n' + '\n'.join(lines) + '\n</p>\n\n'
            + '<details>\n<summary>' + summary + '</summary>\n\n'
            + '\n'.join(captions) + '\n\n</details>\n' + END)

def main():
    root = ET.fromstring(get("https://www.youtube.com/feeds/videos.xml?channel_id=UCSq_SJ128VhRBNt9ClKU9ug"))
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    entries = root.findall("a:entry", ns)[:3]
    if not entries:
        raise RuntimeError("No YouTube videos found")
    updates = []
    for filename, english in (("README.md", False), ("README.en.md", True)):
        path = ROOT / filename
        text = path.read_text(encoding="utf-8")
        if text.count(START) != 1 or text.count(END) != 1:
            raise RuntimeError(f"Exactly one YouTube marker pair required in {filename}")
        text = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: render(entries, ns, english), text, flags=re.S)
        text = text.replace(
            "La selección automática de videos está pendiente de actualizar; el canal enlazado permite consultar las publicaciones actuales.",
            "Selección obtenida del feed público del canal. Cada video enlaza con su publicación original."
        ).replace(
            "The automatic video selection is pending an update; the channel provides access to current uploads.",
            "Selection retrieved from the channel's public feed. Each video links to its original publication."
        )
        updates.append((path, text))
    for path, text in updates:
        path.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
