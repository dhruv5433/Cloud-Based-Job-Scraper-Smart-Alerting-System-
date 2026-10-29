"""
CLOUD COMPUTING: all reads/writes go to Supabase (managed cloud Postgres, DBaaS).
If Supabase is not configured, is_configured() is False and the app falls back
to the local cache so you can still develop offline.
"""
import pandas as pd

from config import get_secret

_client = None
JOB_COLUMNS = ["job_id", "title", "company", "location", "city", "job_type", "salary",
               "description", "job_skills", "url", "source", "posted_date"]


def get_client():
    global _client
    url, key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
    if not url or not key:
        return None
    if _client is None:
        try:
            from supabase import create_client
            _client = create_client(url, key)
        except ImportError:
            return None
    return _client


def is_configured():
    return get_client() is not None


# --------------------------------------------------------------------- jobs
def upsert_jobs(df):
    """Insert new jobs, update existing ones (job_id is the unique key). Returns row count."""
    client = get_client()
    if client is None or df.empty:
        return 0
    rows = []
    for r in df.to_dict("records"):
        posted = r.get("posted_date")
        rows.append({
            "job_id": r["job_id"],
            "title": r["title"],
            "company": r["company"],
            "location": r["location"],
            "city": r.get("city"),
            "job_type": r.get("job_type"),
            "salary": r.get("salary"),
            "description": r["description"],
            "skills": list(r.get("job_skills") or []),
            "url": r.get("url"),
            "source": r.get("source"),
            "posted_date": None if pd.isna(posted) else pd.Timestamp(posted).isoformat(),
        })
    for i in range(0, len(rows), 100):
        client.table("jobs").upsert(rows[i:i + 100], on_conflict="job_id").execute()
    return len(rows)


def get_jobs(limit=1000):
    client = get_client()
    if client is None:
        return pd.DataFrame()
    res = client.table("jobs").select("*").order("posted_date", desc=True).limit(limit).execute()
    return pd.DataFrame(res.data)


# -------------------------------------------------------------------- users
def save_user(profile):
    client = get_client()
    if client is None:
        return False
    client.table("users").upsert({
        "email": profile["email"].strip().lower(),
        "name": profile["name"],
        "skills": profile["skills"],
        "keywords": profile["keywords"],
        "location": profile["location"],
        "watchlist": profile["watchlist"],
    }, on_conflict="email").execute()
    return True


def get_user(email):
    client = get_client()
    if client is None:
        return None
    res = client.table("users").select("*").eq("email", email.strip().lower()).limit(1).execute()
    return res.data[0] if res.data else None


# ------------------------------------------------------------------- alerts
def already_alerted(email):
    client = get_client()
    if client is None:
        return set()
    res = client.table("alerts").select("job_id").eq("user_email", email.strip().lower()).execute()
    return {r["job_id"] for r in res.data}


def log_alerts(email, jobs):
    """jobs: list of (job_id, match_score)."""
    client = get_client()
    if client is None or not jobs:
        return
    rows = [{"user_email": email.strip().lower(), "job_id": j, "match_score": float(s)} for j, s in jobs]
    client.table("alerts").upsert(rows, on_conflict="user_email,job_id").execute()


def get_alert_history(email):
    client = get_client()
    if client is None:
        return pd.DataFrame()
    res = (client.table("alerts").select("*").eq("user_email", email.strip().lower())
           .order("sent_at", desc=True).limit(50).execute())
    return pd.DataFrame(res.data)
