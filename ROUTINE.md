# Routine — how the dashboard updates itself

The pipeline has **two stages**, both free, running daily:

1. **Fetch (GitHub Actions)** — `.github/workflows/fetch.yml` runs `scripts/fetch_feeds.py`
   on GitHub's open-internet runners at **04:40 UTC**. It reads `feeds.json` (news + social
   sources), fetches every RSS feed, and writes **`data/raw.json`** (raw items). Committed to `main`.
2. **Curate (Claude cloud routine)** — at **05:00 UTC** the scheduled routine reads
   `data/raw.json`, then summarizes + categorizes + curates it into **`docs/data/news.json`**
   and pushes. GitHub Pages auto-republishes.

> Why two stages? The routine's cloud sandbox blocks direct web access (egress is locked to a
> security allowlist), so it can't fetch feeds itself. Actions does the fetching; the routine is
> the "brain" that reads the fetched data and does the AI work. No API key, no cost either side.

---

## Run prompt (this is what the scheduled routine runs — paste as the trigger's instructions)

```
You are the curation routine for the "Creative Industry Watcher" dashboard. The repo is cloned
into your working directory. You do NOT have web access — do not try to fetch feeds. Instead a
GitHub Action has already fetched everything into data/raw.json. Your job: turn that raw data
into docs/data/news.json and push. Work only on the main branch.

1. Read data/raw.json (keys: fetched_at, news[], social[]) and docs/app.js (the CATEGORIES
   array — the taxonomy; use ONLY its slug values). If data/raw.json is missing or empty, do not
   overwrite news.json — just report that the fetch stage produced no data, and stop.

2. From raw.news[], curate for signal. KEEP genuine news: launches, product/tool releases,
   funding rounds, M&A, exec moves, new studios/labels/emerging artists, notable VFX work and
   breakdowns, new creative tech, market/industry data. DROP: product discounts / "X% off"
   promos, SEO buyer's guides, glossary/how-to explainers, straight film/album reviews, listicle
   filler. De-duplicate across sources (keep the best-sourced one).

3. From raw.social[], curate the fediverse (Mastodon) + Google Trends signal:
   - Mastodon items: keep posts that show real activity — new tools, notable work/breakdowns,
     emerging makers, discussion worth surfacing. Use the `author` handle. Skip spam, pure
     reshares, and empty/emoji-only posts.
   - Google Trends items: KEEP ONLY terms clearly relevant to music / VFX / film / TV /
     entertainment (an artist, actor, film, show, game, studio). DROP generic/unrelated terms
     (stocks, politics, sports, weather, disasters). Most days only a few qualify — that's fine.

4. For every kept item write a neutral, factual summary of 12-22 words (rewrite text in your own
   words; never copy verbatim; never exceed ~25 words). Assign EXACTLY ONE category slug:
   - News → the music/vfx/film-tv/cross categories.
   - Social → one of the social-* categories, guided by each item's `hint` but use your judgment
     (social-people = accounts/individuals worth following; social-vfx / social-music = tool &
     work buzz; social-trends = Google Trends terms).
   Add 1-3 short tags. For social items, set `source` to the handle + platform
   (e.g. "@artofvfx · Mastodon") or "Google Trends (US)".

5. Aim for ~30-55 news items + ~10-20 social items, weighted to the last ~10 days. Drop anything
   older than ~30 days unless a major ongoing story.

6. Merge with the existing docs/data/news.json: if an item's url already exists, keep its `id`;
   new items get an id from a short source tag + url slug.

7. Write docs/data/news.json as:
   {"generated_at":"<current UTC ISO8601>","items":[{id,title,summary,url,source,published_at,category,tags[]}]}
   Validate it parses as JSON and every item.category is a known slug from docs/app.js.

8. Edit ONLY docs/data/news.json. Stage it, commit "chore: refresh feed <YYYY-MM-DD>", push to
   origin main. If nothing meaningful changed, still bump generated_at and push.

Finish by confirming the push succeeded (or explaining why you didn't push).
```

---

## Taxonomy (source of truth: `docs/app.js` → `CATEGORIES`)

| domain    | slug                | label                     |
|-----------|---------------------|---------------------------|
| music     | `emerging-artists`  | Emerging Artists          |
| music     | `labels-industry`   | Labels & Industry         |
| music     | `music-tech`        | Music Tech & Tools        |
| music     | `trends-culture`    | Trends & Culture          |
| vfx       | `studios-companies` | Studios & Companies       |
| vfx       | `vfx-tech`          | VFX Tech & Tools          |
| vfx       | `notable-work`      | Notable Work & Breakdowns |
| film-tv   | `productions`       | Productions & Greenlights |
| film-tv   | `production-tech`   | Production Tech           |
| film-tv   | `streaming`         | Streaming & Distribution  |
| cross     | `ai-creative`       | AI & Creative Tech        |
| cross     | `business-funding`  | Business & Funding        |
| social    | `social-people`     | People to Watch           |
| social    | `social-vfx`        | VFX & Animation Buzz      |
| social    | `social-music`      | Music-Maker Buzz          |
| social    | `social-trends`     | Spiking Searches          |

## Files
- `feeds.json` — news `feeds[]` + `social[]` sources. Edit to add/remove.
- `scripts/fetch_feeds.py` — the fetcher (runs in Actions).
- `data/raw.json` — fetch output (intermediate; not published).
- `docs/data/news.json` — the published, curated data the site reads.

## Tuning
- Add sources in `feeds.json`. Mastodon = any instance's `/tags/<tag>.rss`.
- Change cadence: edit the cron in `.github/workflows/fetch.yml` (fetch) and the routine's
  schedule (curate) — keep the routine ~20 min after the fetch.
- PMC feeds (Variety, Deadline, THR, IndieWire) may or may not fetch from GitHub's IPs; the
  script skips whatever fails.
