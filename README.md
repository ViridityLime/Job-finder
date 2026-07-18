# job-watcher

Polls your target companies' public job-board APIs, filters for the roles you
want, and pushes a phone notification the moment a new one appears. Runs free
on GitHub Actions on a schedule - no server.

Realistic latency is 5-20 minutes (it polls; GitHub queues scheduled jobs),
which is plenty fast for applying early.

## What each run does

Fetch every company's open jobs -> keep titles matching your keywords (and,
optionally, locations) -> diff against the IDs seen on previous runs -> push a
notification for anything new -> commit the updated seen-set back to the repo.

## Supported sources

| ats              | how to configure                                              |
|------------------|---------------------------------------------------------------|
| greenhouse       | `token:` (slug from boards.greenhouse.io/**slug**)            |
| lever            | `token:` (jobs.lever.co/**slug**)                             |
| ashby            | `token:` (jobs.ashbyhq.com/**slug**)                          |
| smartrecruiters  | `token:` (jobs.smartrecruiters.com/**ID**)                    |
| recruitee        | `token:` (**slug**.recruitee.com)                             |
| workday          | `tenant:` `dc:` `site:` (see below)                           |
| amazon           | no token (uses amazon.jobs, covers AWS)                       |
| shopify          | no token; parses postings from the careers page HTML         |
| custom           | implement `custom()` in adapters.py per site                  |

### Finding Workday coordinates

A company's careers link redirects to
`https://{tenant}.{dc}.myworkdayjobs.com/{locale}/{site}`. Read the three parts
straight from that URL. Example: `rbc.wd3.myworkdayjobs.com/en-US/RBCGLOBAL1`
-> `tenant: rbc`, `dc: wd3`, `site: RBCGLOBAL1`.

## Your companies (researched July 2026)

Already wired up in `config.yaml`:
- **Greenhouse:** Databricks
- **Ashby:** Wealthsimple
- **SmartRecruiters:** CPP Investments
- **Workday:** RBC, TD, CIBC (verify site slug), Capital One, BlackBerry, Cisco
- **amazon.jobs:** Amazon / AWS
- **HTML-parsed:** Shopify (postings live in the page HTML, no API)

Left as commented `custom` stubs (bespoke sites, no standard API - implement
`custom()` when you want them): Scotiabank, AMD (Phenom), Nokia (Oracle),
Home Depot, Deloitte.

Shopify has no API, but its careers page embeds every posting as a
`/careers/{slug}_{uuid}` link, so the `shopify` adapter fetches that page and
parses them out. It rebuilds the title from the slug and can't read a location,
so its config uses `skip_location: true`. This is HTML parsing, so it's more
fragile than the JSON sources - if Shopify restructures the page, it may need a
regex tweak.

## Setup

1. **Create a repo** and push these files.
2. **Pick a notifier:**
   - **ntfy (free):** install the ntfy app, pick a secret topic (e.g.
     `frank-jobs-x9f2q7`), subscribe to it. Keep the topic private.
   - **Telegram (free):** `@BotFather` -> new bot -> token; get your chat id
     from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. **Add repo secrets** (Settings -> Secrets and variables -> Actions):
   ntfy `NTFY_TOPIC`; or Telegram `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.
   (If both are set, Telegram wins.)
4. **Review `config.yaml`** - verify the CIBC site slug and any token before
   trusting it; tune `keywords` and `locations`.
5. **Enable Actions**, then hit **Run workflow** for the first run.

## First run

Seeds state with everything currently open and pushes nothing (so you don't get
a flood for already-open jobs); it prints the current matches to the Actions
log. Every later run notifies only on new postings. Re-seed by deleting
`state/seen.json`. Force first-run pushes with env `NOTIFY_ON_FIRST_RUN=1`.

## Filters

- **keywords:** title must contain one (case-insensitive substring). Preloaded
  for data / PM / investment analyst / ML / quant roles.
- **locations:** must contain one. Tuned for US + Ontario. US location strings
  vary by board, so treat it as a starter and add hubs you care about.
  `canada` is deliberately excluded (it would let in every province); Ontario
  cities are listed explicitly. Set `locations: []` to accept everywhere.
- Big Workday boards (Capital One, Cisco) are queried once per keyword via
  Workday's server-side search to stay light, so keep keywords sensible - a
  role only surfaces if Workday's search matches one of them.

## Local testing

```bash
pip install -r requirements.txt
python test_logic.py    # offline: filter + dedup logic
python monitor.py       # live: hits real APIs, prints (no push unless env set)
```

## Notes

- `state/seen.json` grows over time (closed jobs keep their IDs); it's just
  strings, not worth pruning for personal use. Its commits also keep the
  scheduled workflow from auto-disabling after 60 days of inactivity.
- Public ATS/Workday APIs are built to be read, so a 15-minute poll won't get
  you rate-limited. amazon.jobs and any custom scrape are greyer - stay gentle.
- The amazon adapter and Workday URL format are coded defensively but untested
  against a live board here; eyeball the first real notification's link.
