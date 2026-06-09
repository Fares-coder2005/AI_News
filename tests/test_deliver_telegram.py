"""Test Telegram delivery: section-based sending, HTML escaping, length limits, fallback."""
import sys, os
sys.path.insert(0, 'A:/HemresProjects/AI_News/src')
os.environ['TELEGRAM_BOT_TOKEN'] = 'test_bot'
os.environ['TELEGRAM_CHAT_ID'] = 'test_chat'

import deliver
import requests

captured = []


def fake_post(url, json=None, timeout=None):
    captured.append({"url": url, "payload": json})
    return type("R", (), {
        "status_code": 200,
        "text": '{"ok":true,"result":{"message_id":999}}',
        "ok": True,
        "json": lambda self: {"ok": True, "result": {"message_id": 999}},
    })()


requests.post = fake_post


def build_item(i):
    return {
        "category_label": ["💰 Investment & Funding", "🔬 Patent", "📄 Research Paper", "💬 Opinion & Analysis", "📰 News"][i % 5],
        "score": 10 - (i % 11),
        "title": f"Item {i}: <b>bold</b> & 'quoted' > weird chars",
        "tldr": f"TL;DR {i} with <i>embedded</i> and & and >",
        "link": f"https://example.com/{i}?a=1&b=2",
    }


def test_section_send_counts():
    captured.clear()
    items = [build_item(i) for i in range(25)]
    result = deliver.send_telegram_by_section(items, max_items_per_section=10)
    assert result["sections_sent"] == 5
    assert result["ok"] is True
    assert len(result["message_ids"]) == 5
    print("PASS: section_send_counts")


def test_section_html_structure():
    captured.clear()
    items = [
        {"category_label": "📰 News", "score": 7, "title": "A & B < x", "tldr": "TL;DR with 'quotes' and &", "link": "https://example.com/?a=1&b=2"},
        {"category_label": "💰 Investment & Funding", "score": 5, "title": "Funding round", "tldr": "", "link": ""},
    ]
    result = deliver.send_telegram_by_section(items, max_items_per_section=10)
    assert result["sections_sent"] == 2
    texts = [c["payload"]["text"] for c in captured]
    assert any('AI Weekly Digest — 📰 News' in t for t in texts)
    assert any('AI Weekly Digest — 💰 Investment &amp; Funding' in t for t in texts)
    assert any('parse_mode' in c["payload"] for c in captured)
    news_text = [t for t in texts if 'AI Weekly Digest — 📰 News' in t][0]
    assert '<b>[7/10]</b> A &amp; B &lt; x' in news_text
    assert 'href="https://example.com/?a=1&amp;b=2"' in news_text
    print("PASS: section_html_structure")


def test_section_empty_fields():
    captured.clear()
    items = [
        {"category_label": "📰 News", "score": 4, "title": "", "tldr": "", "link": ""},
        {"category_label": "📰 News", "score": 3, "title": "Title only", "tldr": "", "link": ""},
    ]
    result = deliver.send_telegram_by_section(items, max_items_per_section=10)
    assert result["sections_sent"] == 1
    texts = [c["payload"]["text"] for c in captured]
    assert any("https://example.com" in t for t in texts)
    print("PASS: section_empty_fields")


def test_section_length_limit():
    captured.clear()
    long_title = "x" * 500
    long_tldr = "y" * 500
    items = [{"category_label": "📰 News", "score": 6, "title": long_title, "tldr": long_tldr, "link": "https://example.com"}]
    result = deliver.send_telegram_by_section(items, max_items_per_section=10)
    assert result["sections_sent"] == 1
    texts = [c["payload"]["text"] for c in captured]
    for t in texts:
        assert len(t) <= 4096
    print("PASS: section_length_limit")


def test_send_telegram_backward_compat():
    captured.clear()
    deliver._send_with_fallback = lambda text: {"ok": True, "result": {"message_id": 123}}
    r = deliver.send_telegram([{"category_label": "📰 News", "score": 1, "title": "t", "tldr": "d", "link": "https://example.com"}])
    assert r["result"]["message_id"] == 123
    print("PASS: send_telegram_backward_compat")


if __name__ == "__main__":
    test_section_send_counts()
    test_section_html_structure()
    test_section_empty_fields()
    test_section_length_limit()
    test_send_telegram_backward_compat()
    print("\nAll tests passed.")
