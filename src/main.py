"""
AI Weekly Digest - Main Orchestrator
"""
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from fetch import fetch_all_items
from curate import curate
from deliver import send_telegram_by_section, send_email

load_dotenv()


def _notify_admin_error(subject: str, payload: str) -> None:
    """Send error notification to admin via Telegram with full HTML formatting."""
    try:
        import requests
        import html as _html_mod
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            return
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
        text = (
            "<b>🚨 AI Weekly Digest Error — " + _html_mod.escape(subject) + "</b>\n"
            + "Time: " + now + "\n\n"
            + "<pre>" + _html_mod.escape(payload) + "</pre>"
        )
        requests.post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
    except Exception as e:
        print("[notify] error notify failed:", e)


def _capture_traceback(e: Exception) -> str:
    """Return full traceback as string."""
    return "".join(traceback.format_exception(type(e), e, e.__traceback__))


def main() -> dict:
    print("=" * 50)
    print("AI Weekly Digest — starting")
    print("=" * 50)

    result = {
        "status": "success",
        "items_sent": 0,
        "telegram": None,
        "email": None,
    }

    try:
        # Stage 1: Fetch
        print("\n[main] Fetching items from RSS feeds...")
        items = fetch_all_items(days=7)
        print("[main] Fetched", len(items), "AI-relevant items")

        if not items:
            print("[main] No items found — nothing to do.")
            return {"status": "no_items", "items": 0}

        # Stage 2: Curate
        MAX_ITEMS = 10
        curated = curate(items, max_items=MAX_ITEMS)
        print("[main] Curated down to", len(curated), "items")

        if not curated:
            print("[main] Curation returned empty — nothing to send.")
            return {"status": "no_curated", "items": 0}

        result["items_sent"] = len(curated)

        # Stage 3: Telegram
        print("\n[main] Sending Telegram...")
        try:
            tg_result = send_telegram_by_section(curated, max_items_per_section=10)
            status = "sent" if tg_result.get("ok") else "failed"
            print(
                "[main] Telegram status=",
                status,
                "sent=",
                tg_result.get("sections_sent"),
                "failed=",
                len(tg_result.get("sections_failed", [])),
            )
            result["telegram"] = {
                "status": status,
                "message_ids": tg_result.get("message_ids"),
                "sections_sent": tg_result.get("sections_sent"),
                "sections_failed": tg_result.get("sections_failed"),
            }
            if status == "failed":
                _notify_admin_error(
                    "Telegram Send Failed",
                    "send_telegram_by_section returned ok=False\n\nDetails:\n" + repr(tg_result),
                )
        except Exception as e:
            tb = _capture_traceback(e)
            print("[main] Telegram FAILED:", e)
            result["telegram"] = {"status": "failed", "error": str(e)}
            _notify_admin_error("Telegram Send Exception", tb)

        # Stage 4: Email
        print("\n[main] Sending Email...")
        try:
            email_result = send_email(curated)
            if email_result:
                print("[main] Email sent to", email_result.get("to"))
            result["email"] = email_result
        except Exception as e:
            tb = _capture_traceback(e)
            print("[main] Email FAILED:", e)
            result["email"] = {"status": "failed", "error": str(e)}
            _notify_admin_error("Email Send Exception", tb)

    except Exception as e:
        # Catch-all for fetch/curate/any unexpected error
        tb = _capture_traceback(e)
        print("[main] PIPELINE FAILED:", e)
        result["status"] = "failed"
        result["error"] = str(e)
        _notify_admin_error("Pipeline Exception", tb)

    print("\n[main] Done!", result.get("items_sent", 0), "items delivered.")
    return result


if __name__ == "__main__":
    main()