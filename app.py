"""Streamlit dashboard: profile -> matches, analytics, skill gap, email alerts, data pipeline."""
import altair as alt
import pandas as pd
import streamlit as st

import alerts
import analytics
import db
import sources

ACCENT = "#14B8A6"
ACCENT_2 = "#6366F1"

st.set_page_config(page_title="Smart Job Alerts", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2.2rem; max-width: 1250px;}
.hero {padding: 1.6rem 1.8rem; border-radius: 16px; margin-bottom: 1.2rem;
       background: linear-gradient(120deg, #0F2A3F 0%, #1B2A5E 55%, #2B1F5C 100%);
       border: 1px solid #25406a;}
.hero h1 {margin: 0; font-size: 2rem; letter-spacing: -0.5px;}
.hero p {margin: .4rem 0 0 0; color: #AFC2DE; font-size: 1rem;}
.tag {display:inline-block; padding: 2px 10px; margin: 6px 6px 0 0; border-radius: 999px;
      font-size: .75rem; background: rgba(20,184,166,.15); color: #5EEAD4; border: 1px solid rgba(20,184,166,.35);}
.tag.miss {background: rgba(244,114,182,.12); color:#F9A8D4; border-color: rgba(244,114,182,.3);}
.score {font-size: 2.1rem; font-weight: 700; color: #5EEAD4; line-height: 1;}
.muted {color: #8EA0BC; font-size: .9rem;}
.step {font-size: .8rem; color: #5EEAD4; font-weight: 700; letter-spacing: 1px;}
div[data-testid="stMetric"] {background: #131C2E; border: 1px solid #23304A; padding: 14px 18px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_jobs():
    df, origin = pd.DataFrame(), "Local cache"
    if db.is_configured():
        try:
            df = db.get_jobs()
            origin = "Supabase"
        except Exception as e:
            st.warning(f"Cloud DB read failed, using local cache: {e}")
    if df.empty:
        df, origin = sources.load_cached_jobs(), "Local cache"
    return analytics.prepare_jobs(df), origin


# ------------------------------------------------------------------ chart helpers
def _frame(series):
    df = series.rename_axis("label").reset_index(name="count")
    df["label"] = df["label"].astype(str)
    return df


def hbar(series, color=ACCENT):
    df = _frame(series)
    return (alt.Chart(df).mark_bar(color=color, cornerRadiusEnd=5)
            .encode(x=alt.X("count:Q", title=None), y=alt.Y("label:N", sort="-x", title=None),
                    tooltip=["label", "count"]).properties(height=max(180, 32 * len(df))))


def vbar(series, color=ACCENT_2):
    df = _frame(series)
    return (alt.Chart(df).mark_bar(color=color, cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
            .encode(x=alt.X("label:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("count:Q", title=None), tooltip=["label", "count"]).properties(height=260))


def donut(series):
    df = _frame(series)
    return (alt.Chart(df).mark_arc(innerRadius=60)
            .encode(theta="count:Q", color=alt.Color("label:N", title=None,
                    scale=alt.Scale(range=[ACCENT, ACCENT_2, "#F59E0B", "#EC4899"])),
                    tooltip=["label", "count"]).properties(height=260))


def tags(items, cls=""):
    if not items:
        return '<span class="muted">none</span>'
    return "".join(f'<span class="tag {cls}">{i}</span>' for i in items)


# ------------------------------------------------------------------------ sidebar
jobs, origin = load_jobs()
ROLES = ["data analyst", "data scientist", "data engineer", "business analyst", "software engineer",
         "python developer", "backend developer", "frontend developer", "full stack developer",
         "machine learning engineer", "devops engineer", "cloud engineer", "web developer", "qa engineer"]
COMPANY_OPTIONS = sorted(jobs["company"].dropna().unique(), key=str.lower) if not jobs.empty else []

with st.sidebar:
    st.header("Your profile")
    with st.form("profile_form"):
        name = st.text_input("Name")
        email = st.text_input("Email (alerts go here)")
        skills = st.multiselect("Skills", sorted(analytics.SKILLS), default=["python", "sql", "excel"])
        keywords = st.multiselect("Job roles you want", ROLES, default=["data analyst"])
        location = st.text_input("Location", "Delhi NCR")
        watchlist = st.multiselect("Companies to track (optional)", COMPANY_OPTIONS)
        include_remote = st.checkbox("Include remote jobs", value=True)
        submitted = st.form_submit_button("Save and find jobs", use_container_width=True, type="primary")

    if submitted:
        if not alerts.valid_email(email):
            st.error("Please enter a valid email.")
        elif not skills:
            st.error("Pick at least one skill.")
        else:
            st.session_state["profile"] = {
                "name": name, "email": email.strip().lower(),
                "skills": [x.lower() for x in skills], "keywords": ", ".join(keywords),
                "location": location, "watchlist": [w.lower() for w in watchlist],
                "include_remote": include_remote,
            }
            try:
                if db.save_user(st.session_state["profile"]):
                    st.toast("Profile saved to cloud database")
            except Exception as e:
                st.warning(f"Could not save profile to cloud DB: {e}")

p = st.session_state.get("profile")

# ------------------------------------------------------------------------- hero
st.markdown("""
<div class="hero">
  <h1>Cloud-Based Job Scraper &amp; Smart Alerting System</h1>
  <p>Collects jobs from public APIs, stores them in a cloud database, ranks them against your skills
  with machine-learning text matching, and emails you the best ones.</p>
  <span class="tag">Cloud Computing</span><span class="tag">Data Communication</span>
  <span class="tag">Computational Data Analytics</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------- landing
if not p:
    st.subheader("How it works")
    cols = st.columns(4)
    steps = [("01", "Collect", "Adzuna and Remotive REST APIs are called over HTTPS and mapped into one common schema."),
             ("02", "Store", "Jobs are upserted into Supabase, a managed cloud Postgres database."),
             ("03", "Match", "Skills are extracted from each posting, then ranked with TF-IDF and cosine similarity."),
             ("04", "Alert", "Top matches are emailed over SMTP with TLS. Already-sent jobs are never repeated.")]
    for c, (n, t, d) in zip(cols, steps):
        with c.container(border=True):
            st.markdown(f'<div class="step">STEP {n}</div>', unsafe_allow_html=True)
            st.markdown(f"**{t}**")
            st.markdown(f'<span class="muted">{d}</span>', unsafe_allow_html=True)
    st.info("Fill in your profile in the sidebar and press **Save and find jobs** to see your matches.")

# -------------------------------------------------------------------- dashboard
else:
    if jobs.empty:
        st.info("No jobs found yet. Open the Data Pipeline tab and fetch some.")
        scored = pd.DataFrame()
    else:
        pool, msg = analytics.filter_by_location(jobs, p["location"], p["include_remote"])
        if msg:
            st.info(msg)
        scored = analytics.score_jobs(pool, p["skills"], f"{' '.join(p['skills'])} {p['keywords']}", p["watchlist"])

        st.markdown(f"#### Results for {p['name'] or p['email']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Jobs analysed", len(scored))
        m2.metric("Best match", f"{scored['match_score'].max():.0f}%")
        m3.metric("Average match", f"{scored['match_score'].mean():.0f}%")

    t1, t2, t3, t4, t5 = st.tabs(["Top matches", "Market analytics", "Skill gap", "Alerts", "Data pipeline"])

    with t1:
        if scored.empty:
            st.write("Nothing to show yet.")
        else:
            st.subheader("Your best 5")
            for _, r in scored.head(5).iterrows():
                with st.container(border=True):
                    a, b, c = st.columns([5, 1.2, 1])
                    star = "  |  tracked company" if r["is_watched"] else ""
                    a.markdown(f"**{r['title']}**")
                    a.markdown(f'<span class="muted">{r["company"]}  |  {r["location"]}  |  {r["salary"]}  |  '
                               f'{r["source"]}{star}</span>', unsafe_allow_html=True)
                    a.markdown("You have: " + tags(r["matched"]) + "&nbsp;&nbsp;Missing: " + tags(r["missing"][:6], "miss"),
                               unsafe_allow_html=True)
                    b.markdown(f'<div class="score">{r["match_score"]:.0f}%</div><div class="muted">match</div>',
                               unsafe_allow_html=True)
                    if r["url"]:
                        c.link_button("Apply", r["url"], use_container_width=True)

            st.subheader("All matches")
            show = scored.head(50).copy()
            show["matched"] = show["matched"].map(", ".join)
            show["missing"] = show["missing"].map(", ".join)
            st.dataframe(
                show[["title", "company", "location", "salary", "source", "match_score", "matched", "missing", "url"]],
                hide_index=True, use_container_width=True,
                column_config={
                    "match_score": st.column_config.ProgressColumn("Match %", min_value=0, max_value=100, format="%.0f"),
                    "url": st.column_config.LinkColumn("Apply", display_text="Open"),
                })

    with t2:
        if scored.empty:
            st.write("Nothing to show yet.")
        else:
            a, b = st.columns(2)
            with a.container(border=True):
                st.markdown("**Top skills in demand**")
                st.altair_chart(hbar(analytics.skill_demand(scored)), use_container_width=True)
            with b.container(border=True):
                st.markdown("**Jobs per city**")
                st.altair_chart(hbar(analytics.jobs_by_city(scored), ACCENT_2), use_container_width=True)
            c, d = st.columns(2)
            with c.container(border=True):
                st.markdown("**Match score distribution**")
                st.altair_chart(vbar(analytics.score_distribution(scored)), use_container_width=True)
            with d.container(border=True):
                st.markdown("**Jobs per source**")
                st.altair_chart(donut(scored["source"].value_counts()), use_container_width=True)

    with t3:
        if scored.empty:
            st.write("Nothing to show yet.")
        else:
            gap = analytics.skill_gap(scored.head(10))
            have = sorted(p["skills"])
            st.markdown("**Your skills**")
            st.markdown(tags(have), unsafe_allow_html=True)
            st.write("")
            if gap.empty:
                st.success("You already cover the skills in your top matches.")
            else:
                with st.container(border=True):
                    st.markdown("**Skills missing most often in your top 10 matches**")
                    st.altair_chart(hbar(gap, "#F472B6"), use_container_width=True)
                st.info(f"Learning **{gap.index[0]}** would help you the most.")

    with t4:
        if scored.empty:
            st.write("Nothing to show yet.")
        else:
            s1, s2 = st.columns(2)
            n = s1.slider("How many jobs in the alert?", 1, 10, 5)
            min_score = s2.slider("Minimum match %", 0, 100, 20)
            done = db.already_alerted(p["email"]) if db.is_configured() else set(st.session_state.get("sent", set()))
            fresh = scored[(scored["match_score"] >= min_score) & (~scored["job_id"].isin(done))].head(n)
            st.write(f"{len(fresh)} new job(s) ready to send. Jobs already sent are skipped.")
            st.dataframe(fresh[["title", "company", "match_score"]], hide_index=True, use_container_width=True)
            if not alerts.email_configured():
                st.warning("Email isn't configured (set EMAIL_USER and EMAIL_APP_PASSWORD).")
            if st.button("Send alert email now", disabled=fresh.empty, type="primary"):
                payload = fresh[["title", "company", "location", "salary", "match_score",
                                 "matched", "missing", "url"]].to_dict("records")
                ok, info = alerts.send_job_alert(p["email"], p["name"], payload)
                (st.success if ok else st.error)(info)
                if ok:
                    pairs = list(zip(fresh["job_id"], fresh["match_score"]))
                    if db.is_configured():
                        try:
                            db.log_alerts(p["email"], pairs)
                        except Exception as e:
                            st.warning(f"Alert sent but logging failed: {e}")
                    else:
                        st.session_state.setdefault("sent", set()).update(fresh["job_id"])
            if db.is_configured():
                hist = db.get_alert_history(p["email"])
                if not hist.empty:
                    st.subheader("Alert history")
                    st.dataframe(hist[["job_id", "match_score", "sent_at"]], hide_index=True, use_container_width=True)

    with t5:
        st.markdown('<span class="muted">This is the ingestion side of the system: it calls the APIs, cleans the data '
                    'and writes it to the cloud database. The same steps run automatically via scrape_job.py.</span>',
                    unsafe_allow_html=True)
        used, cap = sources.adzuna_calls_used(), sources.ADZUNA_MAX_CALLS
        st.metric("Adzuna calls used", f"{used} / {cap}")
        st.progress(min(used / cap, 1.0) if cap else 0.0)
        kw = st.text_input("Keywords to fetch (comma separated)", "data analyst, python developer")
        where = st.text_input("Adzuna location", "delhi")
        use_adz = st.checkbox("Also spend Adzuna API calls (1 call per keyword)")
        if st.button("Fetch jobs now"):
            with st.spinner("Fetching..."):
                raw, notes = sources.collect_jobs(analytics.parse_list(kw), where, adzuna_refresh=use_adz)
                fresh_df = analytics.prepare_jobs(raw)
                for n_ in notes:
                    st.warning(n_)
                if db.is_configured():
                    try:
                        st.success(f"Saved {db.upsert_jobs(fresh_df)} jobs to the cloud database.")
                    except Exception as e:
                        st.error(f"Cloud save failed: {e}")
                else:
                    st.info("Supabase not configured. Jobs saved to the local cache only.")
                load_jobs.clear()
                st.write(f"Fetched {len(fresh_df)} unique jobs. Reload the page to see them in the matches.")
