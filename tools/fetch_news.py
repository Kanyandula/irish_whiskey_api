#!/usr/bin/env python3
"""Refresh tools/source/news.csv from publisher RSS feeds.

    python3 tools/fetch_news.py && python3 tools/build_db.py

Stores headline, link, publisher and a short excerpt only - never full article
text. The client links out to the publisher.

Run it by hand when the news looks stale. When this API becomes a real backend,
GET /news should proxy these feeds live behind a short cache instead of baking
a snapshot.
"""
import csv
import datetime as dt
import html
import pathlib
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SRC = pathlib.Path(__file__).resolve().parent / "source"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
LIMIT = 20

FEEDS = [
    ("Irish Whiskey Magazine", "https://www.irishwhiskeymagazine.com/feed/"),
    ("The Whiskey Wash", "https://thewhiskeywash.com/feed/"),
    ("Whisky Advocate", "https://whiskyadvocate.com/call/blogs/rss/"),
    ("VinePair", "https://vinepair.com/feed/"),
]

# No single publisher may fill the feed. The Whiskey Wash posts many times a
# day and would otherwise take every slot on recency alone.
PER_PUBLISHER = 6

WHISKEY_RE = re.compile(r"whisk(e)?y|bourbon|distiller", re.I)
IRISH_RE = re.compile(r"\birish\b|\bireland\b", re.I)


def strip_html(s, limit=240):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."
    return s


def parse_date(raw):
    raw = (raw or "").strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60]


def fetch(publisher, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"  FAIL  {publisher}: {e}", file=sys.stderr)
        return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        print(f"  FAIL  {publisher}: malformed feed ({e})", file=sys.stderr)
        return []

    items = []
    for item in root.iter("item"):
        title = strip_html(item.findtext("title"), 200)
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        summary = strip_html(item.findtext("description"))
        # Every feed carries non-whiskey drinks coverage; keep it on topic.
        if not WHISKEY_RE.search(f"{title} {summary}"):
            continue
        published = parse_date(item.findtext("pubDate"))
        items.append({
            "id": f"{published or 'undated'}-{slugify(publisher)}-{slugify(title)}",
            "title": title,
            "summary": summary,
            "url": link,
            "source": publisher,
            "published": published,
            "image_url": "",
        })
    print(f"  {publisher}: {len(items)} items")
    return items


def main():
    all_items = []
    for publisher, url in FEEDS:
        all_items.extend(fetch(publisher, url))

    seen, deduped = set(), []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)

    capped, per = [], {}
    for it in sorted(deduped, key=lambda i: i["published"], reverse=True):
        n = per.get(it["source"], 0)
        if n < PER_PUBLISHER:
            per[it["source"]] = n + 1
            capped.append(it)
    deduped = capped

    # Irish items first, then most recent.
    deduped.sort(
        key=lambda i: (bool(IRISH_RE.search(f"{i['title']} {i['summary']}")),
                       i["published"]),
        reverse=True,
    )
    rows = deduped[:LIMIT]
    if not rows:
        print("no items fetched; leaving news.csv untouched", file=sys.stderr)
        return 1

    with (SRC / "news.csv").open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)

    irish = sum(1 for r in rows if IRISH_RE.search(f"{r['title']} {r['summary']}"))
    print(f"\nwrote {len(rows)} items to news.csv ({irish} Irish-related)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
