"""
curate.py - LLM ranking + TL;DR

Sends filtered items to the configured Google Generative AI model
(see MODEL constant below) for scoring, summarizing, and re-categorization.
"""
import os
import json
import re
import google.generativeai as genai

# Default model; can be overridden by setting MODEL env var before import
MODEL = os.getenv("MODEL", "gemma-4-31b-it")

# Configure genai lazily inside curate() so .env has time to load first


CATEGORY_LABELS = {
    "paper": "📄 Research Paper",
    "patent": "🔬 Patent",
    "investment": "💰 Investment & Funding",
    "opinion": "💬 Opinion & Analysis",
    "news": "📰 News",
    "general": "📰 News",
}


def _build_prompt(items: list[dict], max_items: int = 12) -> str:
    """Build the curation prompt for the LLM."""
    if not items:
        return "No items to process."

    # Build numbered list for the LLM
    lines = []
    for i, item in enumerate(items):
        lines.append(
            f"{i+1}. [{item['category'].upper()}] {item['title']}\n"
            f"   URL: {item['link']}\n"
            f"   Snippet: {item['summary']}"
        )
    items_text = "\n\n".join(lines)

    prompt = f"""You are an AI news curator. Your job: pick and rank the most important AI developments from the list below.

Consider these dimensions when scoring:
- Scientific/research significance (new model, breakthrough result)
- Industry impact (big company moves, product launches)
- Investment signals (funding rounds, acquisitions)
- Patent activity (novel technological claims)
- Debate value (controversial opinions, ethical discussions, expert takes)

RULES:
1. Score each item 1-10 on "how important is this for any AI enthusiast this week."
2. Write a 1-sentence TL;DR (max 120 chars) that explains what it's actually ABOUT — not just the title.
3. Tag each item as one of: paper, patent, investment, opinion, news
4. Return the top {max_items} items sorted by score descending.
5. Prioritize DIVERSITY across categories. Include at least 2 papers, 1 patent, 1 investment, 1 opinion if they score ≥ 5.
6. Output STRICT JSON array only, no markdown, no explanation.

JSON format (exactly this shape):
[
  {{
    "idx": <original_number>,
    "score": <int>,
    "tldr": "<one sentence, max 120 chars>",
    "category": "paper|patent|investment|opinion|news"
  }}
]

ITEMS TO RANK:
{items_text}"""
    return prompt


def _parse_llm_json(text: str) -> list[dict]:
    """Extract JSON from LLM response, handling common formatting issues."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON array in text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]}")


def curate(items: list[dict], max_items: int = 12) -> list[dict]:
    """
    Send items to the configured LLM (see MODEL), get ranked + summarized list.
    Returns top-scoring items enriched with tldr and category from the LLM.
    """
    if not items:
        return []

    # Load API key here (not at import time) so main.py's load_env() runs first
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise SystemExit("[curate] ERROR: GEMINI_API_KEY is not set. Put it in your .env file.")
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(MODEL)
    prompt = _build_prompt(items, max_items)

    print(f"[curate] Sending {len(items)} items to {MODEL}...")
    response = model.generate_content(prompt)
    raw = response.text.strip()
    print(f"[curate] {MODEL} response length: {len(raw)} chars")

    ranked = _parse_llm_json(raw)

    # Merge LLM results back with original item data
    result = []
    for r in ranked:
        idx = r.get("idx")
        if idx is None or not (1 <= idx <= len(items)):
            continue
        original = items[idx - 1]
        result.append({
            **original,
            "score": r.get("score", 0),
            "tldr": r.get("tldr", original["summary"][:120]),
            "category_label": CATEGORY_LABELS.get(r.get("category", original["category"]), "📰 News"),
        })

    return result


if __name__ == "__main__":
    # Quick smoke test
    from fetch import fetch_all_items
    items = fetch_all_items()
    top = curate(items[:20])
    print(f"\nCurated {len(top)} items:")
    for item in top:
        print(f"  [{item['score']}] {item['tldr']}")
        print(f"       {item['link']}")
