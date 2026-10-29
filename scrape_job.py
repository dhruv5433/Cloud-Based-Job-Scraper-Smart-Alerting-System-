"""
CLOUD AUTOMATION: run this on a schedule (Render Cron / GitHub Actions) to keep
the cloud database fresh. Run by hand with:

    python scrape_job.py --seed-cache     # push your saved files to Supabase (0 API calls)
    python scrape_job.py                  # Remotive live + Adzuna from cache
    python scrape_job.py --adzuna         # also spend Adzuna calls (use sparingly!)
"""
import argparse

import analytics
import db
import sources

DEFAULT_KEYWORDS = ["data analyst", "python developer"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-cache", action="store_true", help="only upload cached files")
    ap.add_argument("--adzuna", action="store_true", help="call the Adzuna API (limited calls)")
    ap.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS)
    ap.add_argument("--where", default="delhi")
    args = ap.parse_args()

    if args.seed_cache:
        raw = sources.load_cached_jobs()
        notes = []
    else:
        raw, notes = sources.collect_jobs(args.keywords, args.where, adzuna_refresh=args.adzuna)
        raw = raw if not raw.empty else sources.load_cached_jobs()

    df = analytics.prepare_jobs(raw)
    print(f"Collected {len(df)} unique jobs")
    for n in notes:
        print("  note:", n)

    if db.is_configured():
        print(f"Saved {db.upsert_jobs(df)} jobs to Supabase")
    else:
        print("Supabase not configured - nothing uploaded (cache is still saved locally).")
    print(f"Adzuna calls used so far: {sources.adzuna_calls_used()}")


if __name__ == "__main__":
    main()
