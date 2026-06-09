# AI Weekly Digest

Automated AI news aggregator — fetches, curates, and delivers the latest AI stories to your Telegram and email every Saturday night.

## How It Works

1. **Fetch** — Pulls from 30+ RSS feeds across 5 categories (news, research papers, patents, investments, opinion)
2. **Filter** — Keyword gate drops irrelevant items before any LLM call
3. **Curate** — Google Generative AI ranks and summarizes the top 10 items, tagged by category
4. **Deliver** — Telegram (one message per section) + HTML email, both in a single run

## Setup (GitHub Actions)

### 1. Fork or clone this repo

### 2. Add Repository Secrets
Settings → Secrets and variables → Actions → New repository secret:

| Secret | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI key from [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `TELEGRAM_BOT_TOKEN` | For Telegram delivery | From @BotFather |
| `TELEGRAM_CHAT_ID` | For Telegram delivery | Your numeric chat ID (message @userinfobot) |
| `SMTP_HOST` | For email | e.g., `smtp.gmail.com` |
| `SMTP_PORT` | For email | `587` |
| `SMTP_USER` | For email | Your Gmail address |
| `SMTP_PASSWORD` | For email | **Gmail App Password** (not your login password) |
| `EMAIL_TO` | For email | Where to send the digest |
| `EMAIL_FROM` | For email | Same as SMTP_USER |

> **Gmail App Password:** Google Account → Security → 2-Step Verification → App passwords → Create → "Mail"

### 3. Enable GitHub Actions
Actions tab → Enable Actions (if prompted)

### 4. Schedule
Runs automatically every **Saturday 02:00 UTC** via `.github/workflows/weekly.yml`.  
Trigger manually anytime: Actions → AI Weekly Digest → Run workflow.

## Local Development

```bash
# Clone
git clone https://github.com/your-username/AI_News.git
cd AI_News

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add your .env file (copy .env.example and fill in values)
cp .env.example .env
# edit .env with your API keys

# Run once
python src/main.py

# Run tests
python tests/test_deliver_telegram.py
```

## Project Structure

```
src/
  main.py            # Orchestrator (entrypoint)
  fetch.py           # RSS fetcher + keyword filter
  curate.py          # LLM ranking + TL;DR
  deliver.py         # Telegram + email formatters
tests/
  test_deliver_telegram.py
.github/workflows/weekly.yml
requirements.txt
```

## Configuration

- **LLM model:** Set via `MODEL` env var (default: `gemma-4-31b-it`). Any model the `google-generativeai` SDK accepts works (e.g., `gemini-2.0-flash`, `gemma-3-27b-it`).
- **Max items:** Edit `MAX_ITEMS = 10` in `main.py`
- **Schedule:** Edit `.github/workflows/weekly.yml` cron expression

## Sources

- **News:** TechCrunch AI, The Verge, MIT Tech Review, Ars Technica, Wired AI, VentureBeat, Towards Data Science, Hacker News, AI News, AI Weekly
- **Papers:** arXiv cs.AI, cs.CL, cs.LG, cs.CV, cs.RO, cs.MA
- **Patents:** Google Patents RSS (AI/ML/neural/deep learning queries)
- **Investments:** Crunchbase News + Google News funding queries
- **Opinion:** Marginal Revolution, Stratechery, Google News AI op-ed

## License

MIT