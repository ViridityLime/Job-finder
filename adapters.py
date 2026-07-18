"""ATS adapters.

Each adapter has the signature  fetch(cfg, keywords) -> list[job]  where:
  cfg      is the company's entry from config.yaml (dict)
  keywords is the global list of title keywords (lowercased by monitor.py)

Each returns a list of normalized jobs:
    {"id": str, "title": str, "location": str, "url": str}

Simple ATS adapters read cfg["token"] and ignore keywords (they return the
whole board; monitor.py filters). The workday and amazon adapters use
keywords for server-side search, because those boards can hold thousands of
roles and pulling everything each run would be heavy.

All endpoints are public, no-auth JSON APIs (verified 2026).

Finding tokens / Workday coordinates:
  greenhouse/lever/ashby/recruitee : slug from the careers URL
  smartrecruiters                  : company id, e.g. jobs.smartrecruiters.com/<ID>/...
  workday                          : careers page redirects to
      https://{tenant}.{dc}.myworkdayjobs.com/{locale}/{site}
      e.g. rbc.wd3.myworkdayjobs.com/en-US/RBCGLOBAL1
           -> tenant rbc, dc wd3, site RBCGLOBAL1
"""
import re

import requests

TIMEOUT = 25
HEADERS = {"User-Agent": "job-watcher (personal job-alert script)"}


def _get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------
# Simple ATS: one GET, return the whole board (monitor.py filters)
# --------------------------------------------------------------------------
def greenhouse(cfg, keywords):
    token = cfg["token"]
    data = _get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    return [
        {
            "id": str(j["id"]),
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
        }
        for j in data.get("jobs", [])
    ]


def lever(cfg, keywords):
    token = cfg["token"]
    data = _get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    out = []
    for j in data:
        cats = j.get("categories", {}) or {}
        out.append(
            {
                "id": str(j["id"]),
                "title": j.get("text", ""),
                "location": cats.get("location", ""),
                "url": j.get("hostedUrl", ""),
            }
        )
    return out


def ashby(cfg, keywords):
    token = cfg["token"]
    data = _get(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    out = []
    for j in data.get("jobs", []):
        url = j.get("jobUrl") or j.get("applyUrl") or j.get("jobPostingUrl", "")
        out.append(
            {
                "id": str(j.get("id", "")),
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": url,
            }
        )
    return out


def smartrecruiters(cfg, keywords):
    token = cfg["token"]
    out, offset = [], 0
    while True:
        data = _get(
            f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
            params={"limit": 100, "offset": offset},
        )
        content = data.get("content", [])
        for j in content:
            loc = j.get("location", {}) or {}
            loc_str = ", ".join(x for x in [loc.get("city"), loc.get("country")] if x)
            jid = str(j.get("id", ""))
            out.append(
                {
                    "id": jid,
                    "title": j.get("name", ""),
                    "location": loc_str,
                    "url": f"https://jobs.smartrecruiters.com/{token}/{jid}",
                }
            )
        offset += len(content)
        if not content or offset >= data.get("totalFound", 0):
            break
    return out


def recruitee(cfg, keywords):
    token = cfg["token"]
    data = _get(f"https://{token}.recruitee.com/api/offers/")
    return [
        {
            "id": str(j.get("id", "")),
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("careers_url") or j.get("careers_apply_url", ""),
        }
        for j in data.get("offers", [])
    ]


# --------------------------------------------------------------------------
# Workday: POST search, one query per keyword to keep big boards light
# --------------------------------------------------------------------------
def workday(cfg, keywords):
    tenant, dc, site = cfg["tenant"], cfg["dc"], cfg["site"]
    locale = cfg.get("locale", "en-US")
    host = f"https://{tenant}.{dc}.myworkdayjobs.com"
    api = f"{host}/wday/cxs/{tenant}/{site}/jobs"
    headers = {**HEADERS, "Content-Type": "application/json",
               "Accept": "application/json"}

    queries = keywords or [""]
    seen_paths, out = set(), []
    for q in queries:
        offset = 0
        while offset < 200:  # cap per keyword; matches are usually few
            body = {"appliedFacets": {}, "limit": 20, "offset": offset,
                    "searchText": q}
            r = requests.post(api, json=body, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            postings = data.get("jobPostings", [])
            for j in postings:
                path = j.get("externalPath", "")
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                out.append(
                    {
                        "id": path,  # externalPath contains the req number
                        "title": j.get("title", ""),
                        "location": j.get("locationsText", ""),
                        "url": f"{host}/{locale}/{site}{path}",
                    }
                )
            offset += len(postings)
            if not postings or offset >= data.get("total", 0):
                break
    return out


# --------------------------------------------------------------------------
# Amazon / AWS: amazon.jobs public search.json (covers AWS roles too)
# --------------------------------------------------------------------------
def amazon(cfg, keywords):
    queries = keywords or [""]
    seen, out = set(), []
    for q in queries:
        offset = 0
        while offset < 300:
            data = _get(
                "https://www.amazon.jobs/en/search.json",
                params={"base_query": q, "result_limit": 100,
                        "offset": offset, "sort": "recent"},
            )
            jobs = data.get("jobs", [])
            for j in jobs:
                jid = str(j.get("id_icims") or j.get("id", ""))
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                out.append(
                    {
                        "id": jid,
                        "title": j.get("title", ""),
                        "location": j.get("normalized_location")
                        or j.get("location", ""),
                        "url": "https://www.amazon.jobs" + j.get("job_path", ""),
                    }
                )
            offset += len(jobs)
            if not jobs or offset >= data.get("hits", 0):
                break
    return out


# --------------------------------------------------------------------------
# Shopify: bespoke careers site. No JSON API - the postings are baked into
# the page HTML (and its embedded JSON) as links of the form
#   /careers/{slug}_{uuid}
# We fetch the page(s), pull every such link, and rebuild the title from the
# slug (more robust than scraping the visual text). Location isn't reliably
# present, so pair this with skip_location: true in config.yaml.
# --------------------------------------------------------------------------
_SHOPIFY_JOB_RE = re.compile(
    r"/careers/([a-z0-9][a-z0-9-]*)_"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def shopify(cfg, keywords):
    # Default to the main careers page. Add discipline-filtered URLs here if
    # you want to be sure a category is covered:  urls: [ "...", "..." ]
    urls = cfg.get("urls") or ["https://www.shopify.com/careers"]
    seen, out = set(), []
    for page in urls:
        r = requests.get(page, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        for m in _SHOPIFY_JOB_RE.finditer(r.text):
            slug, uid = m.group(1), m.group(2)
            if uid in seen:
                continue
            seen.add(uid)
            out.append(
                {
                    "id": uid,
                    "title": slug.replace("-", " ").title(),
                    "location": "",  # not in the markup; see skip_location
                    "url": f"https://www.shopify.com/careers/{slug}_{uid}",
                }
            )
    return out


def custom(cfg, keywords):
    """Stub for bespoke sites (Shopify, Scotiabank, AMD, Nokia, Home Depot,
    Deloitte...). Find the site's JSON/GraphQL request in browser dev tools
    (Network tab), implement it here returning the normalized shape, and
    dispatch by cfg['name'] or cfg['token'] if you add more than one."""
    raise NotImplementedError(
        f"No custom adapter for {cfg.get('name')!r}. Inspect its careers page "
        "Network tab, find the JSON endpoint, and implement it in custom()."
    )


ADAPTERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "smartrecruiters": smartrecruiters,
    "recruitee": recruitee,
    "workday": workday,
    "amazon": amazon,
    "shopify": shopify,
    "custom": custom,
}
