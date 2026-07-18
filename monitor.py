"""Poll each configured company's ATS and alert on new matching roles.

    python monitor.py

State (job keys already seen) persists in state/seen.json.

First run seeds state with everything currently open and does NOT push
notifications (so you don't get a storm for already-open jobs); it prints the
current matches to the log. Every later run pushes a notification for each
genuinely new matching posting. Set NOTIFY_ON_FIRST_RUN=1 to push on run one.
"""
import json
import os
import sys
from pathlib import Path

import yaml

import adapters
import notify

CONFIG = Path("config.yaml")
STATE = Path("state/seen.json")


def load_config():
    with open(CONFIG) as f:
        return yaml.safe_load(f)


def load_seen():
    return set(json.loads(STATE.read_text())) if STATE.exists() else set()


def save_seen(seen):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(sorted(seen)))


def matches(job, keywords, locations):
    title = job["title"].lower()
    if keywords and not any(k in title for k in keywords):
        return False
    if locations:
        loc = job["location"].lower()
        if not any(l in loc for l in locations):
            return False
    return True


def main():
    cfg = load_config()
    filt = cfg.get("filters", {}) or {}
    keywords = [k.lower() for k in filt.get("keywords", [])]
    locations = [l.lower() for l in filt.get("locations", [])]

    first_run = not STATE.exists()
    seen = load_seen()
    hits = []

    for c in cfg["companies"]:
        name, ats = c["name"], c["ats"]
        fetch = adapters.ADAPTERS.get(ats)
        if fetch is None:
            print(f"! unknown ats '{ats}' for {name}", file=sys.stderr)
            continue
        try:
            jobs = fetch(c, keywords)
        except Exception as e:  # one bad board must not kill the whole run
            print(f"! {name} ({ats}) failed: {e}", file=sys.stderr)
            continue

        # Some sources (e.g. Shopify) don't expose a parseable location;
        # skip_location: true lets those companies through the location gate.
        loc_filter = [] if c.get("skip_location") else locations
        for job in jobs:
            key = f"{name}:{job['id']}"
            is_new = key not in seen
            seen.add(key)
            if is_new and matches(job, keywords, loc_filter):
                hits.append((name, job))

    if first_run and os.environ.get("NOTIFY_ON_FIRST_RUN") != "1":
        print(f"First run: seeded {len(seen)} jobs. "
              f"{len(hits)} currently match your filters:")
        for name, job in hits:
            print(f"  - {name}: {job['title']} ({job['location']})")
    else:
        for name, job in hits:
            print(f"NEW: {name}: {job['title']} ({job['location']})")
            notify.send(name, job)

    save_seen(seen)
    print(f"Done. Tracking {len(seen)} jobs; {len(hits)} match this run.")


if __name__ == "__main__":
    main()
