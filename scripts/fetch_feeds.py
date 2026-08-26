#!/usr/bin/env python3
"""
Fetch all news feeds + social sources listed in feeds.json and write a raw
intermediate file at data/raw.json.

Runs in GitHub Actions (open internet). The cloud routine then reads raw.json
— it cannot fetch the web itself (sandbox egress is locked down), so this
script is the "hands" and the routine is the "brain".

Dependencies: feedparser, requests  (installed in the Action).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
FEEDS_FILE = ROOT / "feeds.json"
OUT_FILE = ROOT / "data" / "raw.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}

NEWS_PER_FEED = 12
SOCIAL_PER_FEED = 8
TIMEOUT = 20


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def to_iso(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        tm = entry.get(key)
        if tm:
            try:
                return datetime(*tm[:6], tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            except Exception:
                pass
    return ""


def fetch(url: str):
    """Fetch a feed and return a parsed feedparser object, or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    except Exception as e:
        print(f"  ! request error: {e}", file=sys.stderr)
        return None
    if resp.status_code >= 400:
        print(f"  ! HTTP {resp.status_code} (final url {resp.url})", file=sys.stderr)
        return None
    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        print(f"  ! no entries parsed (final url {resp.url})", file=sys.stderr)
        return None
    return parsed


def mastodon_handle(link: str) -> str:
    """Mastodon post URLs look like https://instance/@handle/12345 -> @handle@instance."""
    try:
        u = urlparse(link)
        m = re.match(r"/@([^/]+)", u.path)
        if m:
            return f"@{m.group(1)}@{u.netloc}"
    except Exception:
        pass
    return ""


YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def fetch_youtube(cfg, social_out):
    """Discover recently-trending videos per niche query via the YouTube Data API.
    Skips silently if YOUTUBE_API_KEY isn't set (so the pipeline runs without it)."""
    key = os.environ.get("YOUTUBE_API_KEY")
    queries = cfg.get("youtube_queries", [])
    if not queries:
        return
    if not key:
        print("[youtube] YOUTUBE_API_KEY not set — skipping YouTube (add it as a repo secret to enable)",
              file=sys.stderr)
        return
    published_after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for q in queries:
        term = q["q"]
        print(f"[youtube] {term} …", file=sys.stderr)
        try:
            r = requests.get(YT_SEARCH, params={
                "part": "snippet", "type": "video", "q": term, "order": "viewCount",
                "publishedAfter": published_after, "maxResults": 10,
                "relevanceLanguage": "en", "key": key}, timeout=TIMEOUT)
            if r.status_code >= 400:
                print(f"  ! search HTTP {r.status_code}: {r.text[:150]}", file=sys.stderr)
                continue
            ids = [it["id"]["videoId"] for it in r.json().get("items", [])
                   if it.get("id", {}).get("videoId")]
            if not ids:
                continue
            v = requests.get(YT_VIDEOS, params={
                "part": "snippet,statistics", "id": ",".join(ids), "key": key}, timeout=TIMEOUT)
            if v.status_code >= 400:
                print(f"  ! videos HTTP {v.status_code}", file=sys.stderr)
                continue
            vids = []
            for it in v.json().get("items", []):
                sn, st = it.get("snippet", {}), it.get("statistics", {})
                vids.append({
                    "id": it.get("id", ""),
                    "title": sn.get("title", ""),
                    "channel": sn.get("channelTitle", ""),
                    "published": sn.get("publishedAt", ""),
                    "views": int(st.get("viewCount", 0) or 0),
                })
            vids.sort(key=lambda x: x["views"], reverse=True)
            for vd in vids[:6]:
                social_out.append({
                    "platform": "youtube",
                    "source": ("YouTube · " + q.get("tag", "")).strip(" ·"),
                    "author": vd["channel"],
                    "text": strip_html(vd["title"]),
                    "url": f"https://www.youtube.com/watch?v={vd['id']}",
                    "published_at": vd["published"],
                    "hint": "social-youtube",
                    "approx_traffic": f"{vd['views']:,} views",
                })
        except Exception as e:
            print(f"  ! error: {e}", file=sys.stderr)


def main() -> int:
    cfg = json.loads(FEEDS_FILE.read_text())
    news_out, social_out = [], []

    for feed in cfg.get("feeds", []):
        print(f"[news] {feed['name']} …", file=sys.stderr)
        parsed = fetch(feed["url"])
        if not parsed:
            continue
        for entry in parsed.entries[:NEWS_PER_FEED]:
            news_out.append({
                "source": feed["name"],
                "title": strip_html(entry.get("title", "")),
                "url": entry.get("link", ""),
                "published_at": to_iso(entry),
                "excerpt": strip_html(entry.get("summary", ""))[:500],
                "domain_hint": (feed.get("domains") or [""])[0],
            })

    for feed in cfg.get("social", []):
        print(f"[social] {feed['name']} …", file=sys.stderr)
        parsed = fetch(feed["url"])
        if not parsed:
            continue
        platform = feed.get("platform", "")
        for entry in parsed.entries[:SOCIAL_PER_FEED]:
            link = entry.get("link", "")
            author = entry.get("author", "") or ""
            if platform == "mastodon":
                author = mastodon_handle(link) or author
            elif platform == "google-trends":
                # Trends RSS items share the feed URL; build a real explore link per term.
                from urllib.parse import quote
                term = strip_html(entry.get("title", ""))
                geo = "US"
                m = re.search(r"geo=([A-Z]{2})", feed["url"])
                if m:
                    geo = m.group(1)
                link = f"https://trends.google.com/trends/explore?q={quote(term)}&geo={geo}"
            social_out.append({
                "platform": platform,
                "source": feed["name"],
                "author": author,
                "text": strip_html(entry.get("title", "")) or strip_html(entry.get("summary", "")),
                "url": link,
                "published_at": to_iso(entry),
                "hint": feed.get("hint", ""),
                "approx_traffic": entry.get("ht_approx_traffic", ""),
            })

    fetch_youtube(cfg, social_out)

    out = {
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "news": news_out,
        "social": social_out,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nWrote {OUT_FILE.relative_to(ROOT)}: {len(news_out)} news + {len(social_out)} social items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
