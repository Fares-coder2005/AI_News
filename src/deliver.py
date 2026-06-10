"""
deliver.py - Telegram + Email delivery
"""
import html as _html_mod
import os, smtplib, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path

# Load .env from project root
from dotenv import load_dotenv
load_dotenv()

TBOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TCHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_API = "https://api.telegram.org/bot" + TBOT

SMTP_HOST      = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.environ.get("SMTP_PORT") or "587")
SMTP_USER      = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD  = os.environ.get("SMTP_PASSWORD", "")
EMAIL_TO       = os.environ.get("EMAIL_TO", SMTP_USER)
EMAIL_FROM     = os.environ.get("EMAIL_FROM", SMTP_USER)

# LLM model name used in footer lines (kept in sync with curate.py's MODEL)
MODEL = "gemma-4-31b-it"

# Display order for sections in Telegram/email output. Also used as
# fallback category labels when curate's mapping is missing one.
SECTION_ORDER = [
    "💰 Investment & Funding",
    "🔬 Patent",
    "📄 Research Paper",
    "💬 Opinion & Analysis",
    "📰 News",
]

# Background colors per section in the HTML email.
EMAIL_SECTION_COLORS = {
    "Investment & Funding": "#e8f5e9",
    "Patent": "#e3f2fd",
    "Research Paper": "#fff3e0",
    "Opinion & Analysis": "#f3e5f5",
    "News": "#f5f5f5",
}


def _format_section(label: str, items: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [
        "<b>AI Weekly Digest — " + _html_mod.escape(label) + "</b>",
        "<b>" + now + " — " + str(len(items)) + " Items</b>",
        "",
    ]
    for it in items:
        sc = it.get("score", "?")
        title = it.get("title", "") or ""
        tldr  = it.get("tldr", "") or ""
        link  = (it.get("link", "") or "").strip()
        if not link:
            link = "https://example.com"
        safe_link = _html_mod.escape(link, quote=True)
        lines.append("<b>[" + str(sc) + "/10]</b> " + _html_mod.escape(title))
        if tldr:
            lines.append("<i>" + _html_mod.escape(tldr) + "</i>")
        lines.append('<a href="' + safe_link + '">🔗 Read more</a>')
        lines.append("")
    lines.append("<i>Curated with " + MODEL + ".</i>")
    return "\n".join(lines)


def _section_chunks(items: list[dict], max_items_per_section: int = 10):
    by = defaultdict(list)
    for it in items:
        by[it.get("category_label", "📰 News")].append(it)
    for label in SECTION_ORDER:
        grp = by.get(label, [])
        if not grp:
            continue
        yield label, grp[:max_items_per_section]


def _format_telegram(items: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    lines = [
        "<b>📰 AI Weekly Digest</b>",
        "<b>" + now + " — " + str(len(items)) + " Items</b>",
        "",
    ]
    by = defaultdict(list)
    for it in items:
        by[it.get("category_label", "📰 News")].append(it)
    for label in SECTION_ORDER:
        grp = by.get(label, [])
        if not grp:
            continue
        lines.append("<b>" + _html_mod.escape(label) + "</b>")
        for it in grp:
            sc = it.get("score", "?")
            title = it.get("title", "") or ""
            tldr  = it.get("tldr", "") or ""
            link  = (it.get("link", "") or "").strip()
            if not link:
                link = "https://example.com"
            safe_link = _html_mod.escape(link, quote=True)
            lines.append("<b>[" + str(sc) + "/10]</b> " + _html_mod.escape(title))
            if tldr:
                lines.append("<i>" + _html_mod.escape(tldr) + "</i>")
            lines.append('<a href="' + safe_link + '">🔗 Read more</a>')
            lines.append("")
        lines.append("")
    lines.append("<i>Curated with " + MODEL + ".</i>")
    return "\n".join(lines)


def _notify_discord_fallback(error: Exception):
    try:
        url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not url:
            return
        now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
        payload = {
            "content": "🚨 AI Weekly Digest send failed\nTime: " + now + "\nError: " + type(error).__name__ + ": " + str(error)
        }
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _format_error_message(subject: str, error: Exception) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    safe = _html_mod.escape(str(error))
    return (
        "<b>🚨 AI Weekly Digest Error - " + _html_mod.escape(subject) + "</b>\n"
        + "Time: " + now + "\n\n"
        + "<pre>" + safe + "</pre>"
    )


def _send_single(text: str) -> dict:
    r = requests.post(
        TELEGRAM_API + "/sendMessage",
        json={"chat_id": TCHAT, "text": text,
              "disable_web_page_preview": False,
              "parse_mode": "HTML"},
        timeout=20,
    )
    return r


def _send_with_fallback(text: str) -> dict:
    try:
        r = _send_single(text)
        if r.ok:
            return r.json()
        raise ValueError("telegram_bad_status:" + str(r.status_code) + ":" + r.text[:200])
    except Exception as primary:
        fallback = text.replace("https://", "hXXps://").replace("http://", "hXXp://")
        if fallback == text:
            raise primary
        try:
            r = _send_single(fallback)
            if r.ok:
                return r.json()
            raise ValueError("telegram_bad_status:" + str(r.status_code) + ":" + r.text[:200])
        except Exception as e:
            raise ValueError("Both primary and fallback sends failed. Last error: " + str(e)) from e


def send_telegram(items: list[dict]) -> dict:
    text = _format_telegram(items)
    if not TBOT or not TCHAT:
        raise RuntimeError("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    r = _send_with_fallback(text)
    return r


def _send_section(label: str, items: list[dict]) -> dict:
    text = _format_section(label, items)
    if len(text) > 4090:
        text = text[:4087] + "..."
    return _send_with_fallback(text)


def send_telegram_by_section(items: list[dict], max_items_per_section: int = 10) -> dict:
    summary = {"ok": True, "sections_sent": 0, "sections_failed": [], "message_ids": []}
    if not TBOT or not TCHAT:
        raise RuntimeError("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
    if not items:
        return summary
    for label, section_items in _section_chunks(items, max_items_per_section=max_items_per_section):
        try:
            r = _send_section(label, section_items)
            msg_id = r.get("result", {}).get("message_id")
            summary["sections_sent"] += 1
            if msg_id:
                summary["message_ids"].append(msg_id)
        except Exception as e:
            summary["ok"] = False
            summary["sections_failed"].append({"section": label, "error": str(e)})
    return summary


def send_telegram_chunked(items: list[dict], max_items: int = 10) -> dict:
    summary = {"ok": True, "chunks_sent": 0, "chunks_failed": [], "message_ids": []}
    if not items:
        return summary
    for start in range(0, len(items), max_items):
        chunk = items[start:start + max_items]
        text = _format_telegram(chunk)
        if len(text) > 4090:
            text = text[:4087] + "..."
        try:
            r = _send_with_fallback(text)
            msg_id = r.get("result", {}).get("message_id")
            summary["chunks_sent"] += 1
            if msg_id:
                summary["message_ids"].append(msg_id)
        except Exception as e:
            summary["ok"] = False
            summary["chunks_failed"].append({"chunk": start // max_items + 1, "error": str(e)})
    return summary


def _format_email_html(items: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    by = defaultdict(list)
    for it in items:
        by[it.get("category_label", "📰 News")].append(it)
    rows = ""
    for label in SECTION_ORDER:
        grp = by.get(label, [])
        if not grp:
            continue
        # Strip the leading emoji to look up the color (keys don't have emoji).
        plain_label = label.lstrip("💰🔬📄💬📰 ").strip()
        bg = EMAIL_SECTION_COLORS.get(plain_label, "#f5f5f5")
        for it in grp:
            rows += '<tr style="background:' + bg + '">'
            rows += '<td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;width:30px;vertical-align:top;font-size:13px">'
            rows += "<b>" + str(it.get("score", "?")) + "/10</b>"
            rows += "</td>"
            rows += '<td style="padding:10px 12px;border-bottom:1px solid #e0e0e0">'
            rows += '<b style="color:#1a1a2e">' + _html_mod.escape(it.get("title", "")) + "</b><br>"
            rows += '<span style="color:#555;font-size:13px">' + _html_mod.escape(it.get("tldr", "")) + "</span><br>"
            rows += '<a href="' + _html_mod.escape(it.get("link", ""), quote=True)
            rows += '" style="color:#1565c0;font-size:12px">' + _html_mod.escape(it.get("link", "")) + "</a>"
            rows += "</td></tr>"
    return """<html>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333">
<h1 style="color:#1a1a2e">AI Weekly Digest</h1>
<p style="color:#666;font-size:14px">""" + now + """ - """ + str(len(items)) + """ Items</p>
<table style="width:100%;border-collapse:collapse;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden">
  <thead><tr style="background:#1a1a2e;color:white">
    <th style="padding:10px 12px;text-align:left;width:40px;font-size:12px">Score</th>
    <th style="padding:10px 12px;text-align:left;font-size:12px">Story</th>
  </tr></thead><tbody>""" + rows + """</tbody></table>
<p style="color:#999;font-size:11px;margin-top:20px">
  Sources: arXiv, TechCrunch, The Verge, Google Patents, and more.
  Curated with """ + MODEL + """.
</p></body></html>"""


def send_email(items):
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[email] SMTP not configured - skipping.")
        return None
    now = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subj = "AI Weekly Digest - " + now
    html = _format_email_html(items)
    plain = "AI Weekly Digest - " + now + "\n\n" + "\n".join(
        "[" + str(it.get("score","?")) + "/10] " + str(it.get("title",""))
        + "\n" + str(it.get("tldr",""))
        + "\n" + str(it.get("link",""))
        for it in items
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
        srv.starttls()
        srv.login(SMTP_USER, SMTP_PASSWORD)
        srv.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print("[email] sent to " + EMAIL_TO)
    return {"status": "sent", "to": EMAIL_TO}
