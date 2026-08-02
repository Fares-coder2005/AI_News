"""
AI Weekly Digest - Fetch
Sources: RSS feeds across all AI domains (news, research, patents, investments, opinions)
"""
import feedparser
import requests
from datetime import datetime, timezone
from urllib.parse import quote_plus
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


# ─── Feeds ───────────────────────────────────────────────────────────────────

GENERAL_AI_FEEDS = [
    # TechCrunch AI
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    # The Verge (main feed, AI content is included)
    "https://www.theverge.com/rss/index.xml",
    # MIT Technology Review
    "https://www.technologyreview.com/feed/",
    # Ars Technica
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    # Wired AI
    "https://www.wired.com/feed/tag/ai/latest/rss",
    # VentureBeat AI
    "https://venturebeat.com/category/ai/feed/",
    # Towards Data Science
    "https://towardsdatascience.com/feed",
    # Hacker News (Algolia - sort by date for latest)
    "https://hnrss.org/frontpage",
    # AI News
    "https://www.artificialintelligence-news.com/feed/",
    # AI Weekly
    "https://aiweekly.co/feed",
]

RESEARCH_FEEDS = [
    # arXiv AI
    "https://rss.arxiv.org/rss/cs.AI",
    # arXiv Computation and Language
    "https://rss.arxiv.org/rss/cs.CL",
    # arXiv Machine Learning
    "https://rss.arxiv.org/rss/cs.LG",
    # arXiv Computer Vision
    "https://rss.arxiv.org/rss/cs.CV",
    # arXiv Robotics
    "https://rss.arxiv.org/rss/cs.RO",
    # arXiv Multiagent Systems
    "https://rss.arxiv.org/rss/cs.MA",
]

PATENT_FEEDS = [
    # Google Patents - AI keyword searches
    "https://news.google.com/rss/search?q=artificial+intelligence+patent+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=machine+learning+patent+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=neural+network+patent+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=deep+learning+patent+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+patent+filing+when:7d&hl=en-US&gl=US&ceid=US:en",
]

INVESTMENT_FEEDS = [
    # Crunchbase News
    "https://news.crunchbase.com/feed/",
    # AI investment keyword searches via Google News
    "https://news.google.com/rss/search?q=AI+investment+funding+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=artificial+intelligence+startup+funding+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=LLM+funding+billion+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI+acquisition+merger+when:7d&hl=en-US&gl=US&ceid=US:en",
]

OPINION_FEEDS = [
    # Marginal Revolution (Tyler Cowen - often covers AI economics)
    "https://marginalrevolution.com/feed",
    # Stratechery (Ben Thompson - tech strategy, often AI)
    "https://stratechery.com/feed/",
    # AI opinion pieces via Google News
    "https://news.google.com/rss/search?q=AI+opinion+op-ed+when:14d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22artificial+intelligence%22+opinion+analysis+when:14d&hl=en-US&gl=US&ceid=US:en",
]

ALL_FEEDS = {
    "general": GENERAL_AI_FEEDS,
    "research": RESEARCH_FEEDS,
    "patent": PATENT_FEEDS,
    "investment": INVESTMENT_FEEDS,
    "opinion": OPINION_FEEDS,
}

CATEGORY_HINT = {
    "general": "news",
    "research": "paper",
    "patent": "patent",
    "investment": "investment",
    "opinion": "opinion",
}

KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning", "neural network",
    "transformer", "GPT", "OpenAI", "Anthropic", "Claude", "Gemini", "LLM",
    "large language model", "diffusion", "Stable Diffusion", "Midjourney", "DALL-E",
    "AI agent", "autonomous agent", "multimodal", "reinforcement learning",
    "computer vision", "NLP", "natural language processing", "robotics",
    "AI safety", "AI alignment", "AGI", "general intelligence",
    "foundation model", "fine-tuning", "RLHF", "RAG", "retrieval augmented",
    "AI startup", "AI funding", "AI investment", "AI acquisition", "AI patent",
    "DeepMind", "Google AI", "Meta AI", "Microsoft AI", "Apple AI",
    "NVIDIA AI", "chip", "GPU", "TPU", "inference", "AI regulation",
    "EU AI Act", "AI policy", "AI ethics", "bias", "hallucination",
    "Mixtral", "Mistral", "Llama", "Meta Llama", "Qwen", "Mistral",
    "AI chip", "AI hardware", "AI software", "AI tool", "AI product",
    "Copilot", "Bard", "ChatGPT", "Perplexity", "AI search",
    "synthetic data", "AI training", "AI model", "AI release",
    "Open Source AI", "open-source LLM", "Hugging Face",
]

REQUEST_TIMEOUT = 8
FEED_FETCH_TIMEOUT = 10


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    """Lowercase + strip trailing slash for deduping."""
    return url.lower().rstrip("/")


def _matches_keywords(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(kw.lower() in text for kw in KEYWORDS)


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                return datetime(*tp[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _fetch_single_feed(url: str, category: str) -> list[dict]:
    items = []
    try:
        resp = requests.get(url, timeout=FEED_FETCH_TIMEOUT, headers={"User-Agent": "AI-Weekly-Digest/1.0"})
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            summary = entry.get("summary", entry.get("description", "")).strip()
            if not title or not link:
                continue
            # Strip HTML from summary
            summary = re.sub(r"<[^>]+>", "", summary)
            summary = re.sub(r"\s+", " ", summary).strip()
            # Truncate to 300 chars
            if len(summary) > 300:
                summary = summary[:297] + "..."
            items.append({
                "title": title,
                "link": link,
                "summary": summary,
                "category": category,
                "date": _parse_date(entry),
            })
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
    return items


# ─── Public API ──────────────────────────────────────────────────────────────

def fetch_all_items(days: int = 7) -> list[dict]:
    """
    Fetch items from all feeds and return the last `days` days of content.
    Filters to AI-relevant items via keyword gate.
    """
    cutoff = datetime.now(timezone.utc)
    seen: set[str] = set()
    all_items: list[dict] = []

    # Build flat task list
    tasks = []
    for category, feeds in ALL_FEEDS.items():
        for url in feeds:
            tasks.append((url, category))

    # Fetch in parallel with bounded workers to avoid hangs
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_meta = {
            executor.submit(_fetch_single_feed, url, category): (url, category)
            for url, category in tasks
        }
        for future in as_completed(future_to_meta, timeout=45):
            url, category = future_to_meta[future]
            try:
                items = future.result()
            except Exception as e:
                print(f"[WARN] Future failed for {url}: {e}")
                continue
            for item in items:
                norm_link = _normalize_url(item["link"])
                if norm_link in seen:
                    continue
                seen.add(norm_link)
                # Keyword filter — keep anything loosely AI-related
                if _matches_keywords(item["title"], item["summary"]):
                    all_items.append(item)

    # Sort by date descending; items with no date go last
    def _sort_key(item):
        d = item.get("date")
        # Make sure cutoff comparison works
        if d is None or d > cutoff:
            return (1, cutoff)  # treat no-date as recent
        return (0, d)

    all_items.sort(key=_sort_key, reverse=True)
    return all_items


if __name__ == "__main__":
    items = fetch_all_items()
    print(f"Fetched {len(items)} AI-relevant items")
    for item in items[:5]:
        print(f"  [{item['category']}] {item['title']}")
