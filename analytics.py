"""
COMPUTATIONAL DATA ANALYTICS: cleaning, skill extraction, TF-IDF + cosine
similarity matching, and market statistics.
"""
import html
import re

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = [
    "python", "sql", "excel", "power bi", "tableau", "looker", "power query",
    "aws", "azure", "gcp", "docker", "kubernetes", "git", "linux",
    "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
    "statistics", "data analysis", "data visualization", "etl", "spark", "hadoop",
    "pandas", "numpy", "java", "javascript", "c++", "c#", "html", "css", "react",
    "django", "flask", "fastapi", "mongodb", "postgresql", "mysql",
]
_PATTERNS = {s: re.compile(r"(?<![a-z0-9+#])" + re.escape(s) + r"(?![a-z0-9+#])") for s in SKILLS}

CITIES = ["delhi", "noida", "gurgaon", "gurugram", "ghaziabad", "faridabad", "mumbai",
          "pune", "bangalore", "bengaluru", "hyderabad", "chennai", "kolkata", "remote"]
NCR = {"delhi", "noida", "gurgaon", "gurugram", "ghaziabad", "faridabad"}


# ------------------------------------------------------------------ cleaning
def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def find_skills(clean_text):
    return [s for s, p in _PATTERNS.items() if p.search(clean_text)]


def find_city(location):
    loc = str(location or "").lower()
    for c in CITIES:
        if c in loc:
            return c.title()
    if any(w in loc for w in ("anywhere", "worldwide", "remote")):
        return "Remote"
    return "Other"


def prepare_jobs(df):
    """Idempotent: safe to run on fresh API data or data loaded from the DB."""
    cols = ["job_id", "title", "company", "location", "job_type", "salary",
            "description", "url", "source", "posted_date"]
    df = df.copy() if df is not None else pd.DataFrame()
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()
    if df.empty:
        for c in ("clean", "job_skills", "city"):
            df[c] = None
        return df

    df["title"] = df["title"].fillna("")
    df["company"] = df["company"].fillna("Unknown")
    df["description"] = df["description"].map(strip_html)
    clean = (df["title"] + " " + df["description"]).str.lower()
    clean = clean.str.replace(r"[^a-z0-9\s+#]", " ", regex=True)
    df["clean"] = clean.str.replace(r"\s+", " ", regex=True).str.strip()
    df = df.drop_duplicates(subset=["title", "company"]).reset_index(drop=True)
    df["posted_date"] = pd.to_datetime(df["posted_date"], errors="coerce", utc=True)
    df["salary"] = df["salary"].fillna("Not disclosed")
    df["job_skills"] = df["clean"].map(find_skills)
    df["city"] = df["location"].map(find_city)
    return df


def parse_list(text):
    return [x.strip().lower() for x in re.split(r"[,\n]", text or "") if x.strip()]


def filter_by_location(df, location, include_remote=True):
    """Soft filter. Returns (filtered_df, message_or_None)."""
    tokens = [t for t in re.split(r"[,\s]+", (location or "").lower()) if t and t not in ("india",)]
    if not tokens or df.empty:
        return df, None
    wanted = set()
    for t in tokens:
        wanted |= NCR if t == "ncr" else {t}
    loc = df["location"].fillna("").str.lower()
    mask = loc.map(lambda x: any(w in x for w in wanted))
    if include_remote:
        mask |= (df["city"] == "Remote")
    out = df[mask]
    if out.empty:
        return df, "No jobs matched that location, so showing all jobs instead."
    return out.reset_index(drop=True), None


# ------------------------------------------------------------------- scoring
def score_jobs(df, user_skills, user_text, watchlist=None):
    """
    match_score = 0.6 * skill overlap  +  0.4 * TF-IDF cosine similarity (scaled)
    Jobs from watched companies get a +10 bonus (capped at 100).
    """
    df = df.copy()
    if df.empty:
        for c in ("overlap", "tfidf", "match_score", "matched", "missing", "is_watched"):
            df[c] = None
        return df
    user_skills = set(user_skills)

    def overlap(js):
        return len(user_skills & set(js)) / len(js) * 100 if js else 0.0

    df["overlap"] = df["job_skills"].map(overlap)

    tfidf = TfidfVectorizer(stop_words="english")
    matrix = tfidf.fit_transform([user_text or " ".join(user_skills)] + df["clean"].tolist())
    sims = cosine_similarity(matrix[0:1], matrix[1:])[0]
    top = sims.max()
    df["tfidf"] = (sims / top * 100) if top > 0 else 0.0   # scale so best text match = 100

    df["matched"] = df["job_skills"].map(lambda js: sorted(user_skills & set(js)))
    df["missing"] = df["job_skills"].map(lambda js: sorted(set(js) - user_skills))

    watch = [w.lower() for w in (watchlist or [])]
    df["is_watched"] = df["company"].str.lower().map(lambda c: any(w in c for w in watch)) if watch else False

    score = 0.6 * df["overlap"] + 0.4 * df["tfidf"] + df["is_watched"].astype(int) * 10
    df["match_score"] = score.clip(0, 100).round(1)
    return df.sort_values("match_score", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------- statistics
def skill_demand(df, top=10):
    s = df["job_skills"].explode().dropna()
    return s.value_counts().head(top)


def skill_gap(top_df, top=8):
    s = top_df["missing"].explode().dropna()
    return s.value_counts().head(top)


def jobs_by_city(df, top=8):
    return df["city"].value_counts().head(top)


def score_distribution(df):
    bins = pd.cut(df["match_score"], [-1, 20, 40, 60, 80, 100],
                  labels=["0-20", "21-40", "41-60", "61-80", "81-100"])
    return bins.value_counts().reindex(["0-20", "21-40", "41-60", "61-80", "81-100"]).fillna(0).astype(int)
