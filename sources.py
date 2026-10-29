"""
DATA COMMUNICATION: fetches jobs from two REST APIs over HTTPS and maps them
into one common schema.

Adzuna has a small call limit, so it is ONLY called when refresh=True.
Every raw API response is saved in cache/ so we never waste a call.
"""
import glob
import json
import os
import re
import time

import pandas as pd
import requests

from config import get_secret

CACHE_DIR = "cache"
LEGACY_ADZUNA_CACHE = "adzuna_cache.json"   # the file from your first test call
CALL_LOG = os.path.join(CACHE_DIR, "adzuna_calls.txt")
ADZUNA_MAX_CALLS = int(get_secret("ADZUNA_MAX_CALLS", 22))  # keep a few spare out of 25

COLUMNS = ["job_id", "title", "company", "location", "job_type",
           "salary", "description", "url", "source", "posted_date"]


def _slug(*parts):
    return re.sub(r"[^a-z0-9]+", "_", " ".join(parts).lower()).strip("_")


def _save_json(path, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _load_json(path):
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------- Adzuna
def adzuna_calls_used():
    try:
        return int(open(CALL_LOG).read().strip())
    except Exception:
        return 0


def _count_adzuna_call():
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CALL_LOG, "w") as f:
        f.write(str(adzuna_calls_used() + 1))


def map_adzuna(j):
    smin, smax = j.get("salary_min"), j.get("salary_max")
    return {
        "job_id": f"adz_{j.get('id')}",
        "title": j.get("title", ""),
        "company": (j.get("company") or {}).get("display_name", "Unknown"),
        "location": (j.get("location") or {}).get("display_name", ""),
        "job_type": j.get("contract_time") or j.get("contract_type") or "",
        "salary": f"{int(smin)}-{int(smax)}" if smin and smax else None,
        "description": j.get("description", ""),
        "url": j.get("redirect_url", ""),
        "source": "Adzuna",
        "posted_date": j.get("created"),
    }


def fetch_adzuna(keyword, where="delhi", country="in", page=1, refresh=False):
    """Returns a list of mapped jobs. Only hits the API if refresh=True."""
    path = os.path.join(CACHE_DIR, f"adzuna_{_slug(country, keyword, where)}_p{page}.json")

    if not refresh:
        if os.path.exists(path):
            return [map_adzuna(j) for j in _load_json(path).get("results", [])]
        return []

    app_id, app_key = get_secret("ADZUNA_APP_ID"), get_secret("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY are not set")
    if adzuna_calls_used() >= ADZUNA_MAX_CALLS:
        raise RuntimeError(f"Adzuna call budget reached ({ADZUNA_MAX_CALLS}). Using cache only.")

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
    params = {"app_id": app_id, "app_key": app_key, "what": keyword, "where": where,
              "results_per_page": 50, "content-type": "application/json"}
    resp = requests.get(url, params=params, timeout=15)
    _count_adzuna_call()
    resp.raise_for_status()
    data = resp.json()
    _save_json(path, data)
    return [map_adzuna(j) for j in data.get("results", [])]


# --------------------------------------------------------------- Remotive
def map_remotive(j):
    return {
        "job_id": f"rem_{j.get('id')}",
        "title": j.get("title", ""),
        "company": j.get("company_name", "Unknown"),
        "location": j.get("candidate_required_location", "Remote"),
        "job_type": j.get("job_type", ""),
        "salary": j.get("salary") or None,
        "description": j.get("description", ""),
        "url": j.get("url", ""),
        "source": "Remotive",
        "posted_date": j.get("publication_date"),
    }


def fetch_remotive(keyword, limit=50, max_age_hours=6):
    """Free, no key. Cached for a few hours to be polite to the API."""
    path = os.path.join(CACHE_DIR, f"remotive_{_slug(keyword)}.json")
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < max_age_hours * 3600:
        data = _load_json(path)
    else:
        resp = requests.get("https://remotive.com/api/remote-jobs",
                            params={"search": keyword, "limit": limit}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        _save_json(path, data)
    return [map_remotive(j) for j in data.get("jobs", [])]


# ---------------------------------------------------------------- helpers
def to_frame(rows):
    df = pd.DataFrame(rows)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[COLUMNS]


def load_cached_jobs():
    """Builds a DataFrame from everything saved locally. Costs 0 API calls."""
    rows = []
    for p in glob.glob(os.path.join(CACHE_DIR, "adzuna_*.json")):
        rows += [map_adzuna(j) for j in _load_json(p).get("results", [])]
    if os.path.exists(LEGACY_ADZUNA_CACHE):
        rows += [map_adzuna(j) for j in _load_json(LEGACY_ADZUNA_CACHE).get("results", [])]
    for p in glob.glob(os.path.join(CACHE_DIR, "remotive_*.json")):
        rows += [map_remotive(j) for j in _load_json(p).get("jobs", [])]
    df = to_frame(rows)
    return df.drop_duplicates(subset="job_id").reset_index(drop=True)


def collect_jobs(keywords, where="delhi", adzuna_refresh=False):
    """Fetch from both sources for a list of keywords. Returns (DataFrame, [messages])."""
    rows, notes = [], []
    for kw in keywords:
        try:
            rows += fetch_remotive(kw)
        except Exception as e:
            notes.append(f"Remotive '{kw}': {e}")
        try:
            rows += fetch_adzuna(kw, where=where, refresh=adzuna_refresh)
        except Exception as e:
            notes.append(f"Adzuna '{kw}': {e}")
    df = to_frame(rows)
    return df.drop_duplicates(subset="job_id").reset_index(drop=True), notes
