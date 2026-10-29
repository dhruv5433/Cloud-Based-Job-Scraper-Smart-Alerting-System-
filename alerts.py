"""
DATA COMMUNICATION: sends job alerts over SMTP (TLS) using a Gmail App Password.
"""
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import get_secret


def email_configured():
    return bool(get_secret("EMAIL_USER") and get_secret("EMAIL_APP_PASSWORD"))


def valid_email(addr):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", addr or ""))


def build_message(name, jobs):
    """jobs: list of dicts with title, company, location, salary, match_score, matched, missing, url."""
    text = [f"Hi {name or 'there'},", "", "Here are your best job matches today:", ""]
    cards = []
    for j in jobs:
        matched = ", ".join(j["matched"]) or "-"
        missing = ", ".join(j["missing"]) or "none"
        text += [f"{j['title']} at {j['company']} ({j['location']})",
                 f"  Match: {j['match_score']:.0f}%  |  Salary: {j['salary']}",
                 f"  You have: {matched}  |  Missing: {missing}",
                 f"  Apply: {j['url']}", ""]
        cards.append(
            f"<div style='margin-bottom:16px;padding:12px;border:1px solid #ddd;border-radius:8px'>"
            f"<b>{j['title']}</b> at {j['company']}<br>{j['location']} &middot; {j['salary']}<br>"
            f"<b>Match: {j['match_score']:.0f}%</b><br>You have: {matched}<br>Missing: {missing}<br>"
            f"<a href='{j['url']}'>Apply here</a></div>")
    text.append("- Smart Job Alerts")
    html = f"<p>Hi {name or 'there'},</p><p>Here are your best job matches today:</p>{''.join(cards)}"
    return "\n".join(text), html


def send_email(to_email, subject, text, html=None):
    """Returns (ok, message)."""
    if not valid_email(to_email):
        return False, "That doesn't look like a valid email address."
    if not email_configured():
        return False, "EMAIL_USER / EMAIL_APP_PASSWORD are not set."
    user = get_secret("EMAIL_USER")
    password = get_secret("EMAIL_APP_PASSWORD").replace(" ", "")
    host = get_secret("SMTP_HOST", "smtp.gmail.com")
    port = int(get_secret("SMTP_PORT", 465))

    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to_email
    msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())
        return True, f"Alert sent to {to_email}"
    except Exception as e:
        return False, f"Email failed: {e}"


def send_job_alert(to_email, name, jobs):
    text, html = build_message(name, jobs)
    return send_email(to_email, f"{len(jobs)} new job matches for you", text, html)
