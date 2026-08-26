# Routine — how the dashboard updates itself

This file is the **instruction set the scheduled Claude Code routine follows on every run**.
The routine is the "AI" in the pipeline: it fetches feeds, summarizes + categorizes each
item itself (no external API key needed), rewrites `docs/data/news.json`, and pushes to GitHub.
GitHub Pages then serves the updated dashboard automatically.

> When you register the scheduled routine (see `README.md`), paste the **Run prompt** below as
> its instructions. Everything else here is reference the routine reads from the repo.

---

## Run prompt (paste this as the scheduled task's instructions)

```
You are the update routine for the Creative Industry Watcher dashboard. Work inside this repo.

1. Read feeds.json for the list of RSS sources, and docs/app.js for the exact category taxonomy
   (the CATEGORIES array — use its `slug` values, nothing else).

2. Fetch each feed with WebFetch. For each, extract the most recent items (title, url,
   published_at ISO, and the feed's own excerpt). Skip any feed that errors — do not fail the run.
   Known blocked feeds (PMC/tollbit paywall: Variety, Deadline, Hollywood Reporter, IndieWire)
   will 402/redirect — skip them silently; they are kept in feeds.json only as a record.

3. Build the item set:
   - Keep only genuine NEWS with signal: launches, releases, funding, M&A, exec moves,
     new studios/labels/artists, notable VFX work, new creative tech, market data.
   - DROP: pure product deals/discounts, "X% off" posts, buyer's guides that are just SEO,
     glossary/how-to explainers, straight film/album reviews, and horoscope/listicle filler.
   - De-duplicate: if two sources cover the same event, keep the better-sourced one.
   - Write a concise, factual 15-22 word summary for each (rewrite the excerpt; don't copy it
     verbatim, and never exceed ~25 words). Neutral tone, no hype.
   - Assign exactly one category `slug` from the taxonomy. Assign 1-3 short lowercase-ish tags
     (company names, tech, "exec move", "funding round", etc.).

4. Aim for roughly 30-60 items total, weighted toward the last ~10 days. Prefer freshness;
   drop anything older than ~30 days unless it's a major ongoing story.

5. Merge with the previous docs/data/news.json:
   - Keep an item's existing `id` if the same url is already present (stable ids matter).
   - New items get an id derived from a short source tag + url slug.
   - Drop items older than 30 days that no longer appear in any feed.

6. Write the result to docs/data/news.json with this exact shape:
   { "generated_at": "<current UTC ISO8601>", "items": [ {id,title,summary,url,source,published_at,category,tags[]} ] }
   Validate it parses as JSON and every item.category is a known slug.

7. Commit with message "chore: refresh feed <YYYY-MM-DD>" and push to the main branch.
   If nothing meaningful changed, still update generated_at and push (keeps "last updated" honest).

Keep the whole run lightweight. Do not edit any file other than docs/data/news.json.
```

---

## The taxonomy (source of truth is `docs/app.js` → `CATEGORIES`)

| domain    | slug                | label                       |
|-----------|---------------------|-----------------------------|
| music     | `emerging-artists`  | Emerging Artists            |
| music     | `labels-industry`   | Labels & Industry           |
| music     | `music-tech`        | Music Tech & Tools          |
| music     | `trends-culture`    | Trends & Culture            |
| vfx       | `studios-companies` | Studios & Companies         |
| vfx       | `vfx-tech`          | VFX Tech & Tools            |
| vfx       | `notable-work`      | Notable Work & Breakdowns   |
| film-tv   | `productions`       | Productions & Greenlights   |
| film-tv   | `production-tech`   | Production Tech             |
| film-tv   | `streaming`         | Streaming & Distribution    |
| cross     | `ai-creative`       | AI & Creative Tech          |
| cross     | `business-funding`  | Business & Funding          |

To change categories: edit `CATEGORIES` in `docs/app.js` (the UI) — the routine reads it from there,
so the two never drift.

## Data contract (`docs/data/news.json`)

```json
{
  "generated_at": "2026-08-26T14:30:00Z",
  "items": [
    {
      "id": "unique-stable-id",
      "title": "Headline",
      "summary": "One factual sentence, ~15-22 words.",
      "url": "https://source/article",
      "source": "Publication name",
      "published_at": "2026-08-25T16:22:20Z",
      "category": "labels-industry",
      "tags": ["Sony", "exec move"]
    }
  ]
}
```

## Tuning
- Add/remove sources in `feeds.json`.
- Change cadence when you register the routine (daily is a good default for low traffic).
- If you want emerging-artist and streaming coverage to fill out, add sources that publish
  those beats (many majors' feeds are paywalled to fetchers, so favor open trade/blog feeds).
