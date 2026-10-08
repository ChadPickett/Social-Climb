# Social Climb

Pick a topic, hit **Analyze**, and get:

1. **Search plan.** An AI agent turns the topic into Instagram hashtags to research.
2. **Data collection.** Posts for those hashtags from the last 60 days are pulled and cached locally.
3. **Analysis.** Code (not the AI) computes the stats for the 7 / 15 / 30 / 60-day windows: typical vs. top
   likes, comments and views, best format, best weekdays and hours in *your* time zone, caption length,
   the hashtags top performers use, and whether the topic is heating up or cooling down.
4. **Draft post.** A second AI agent writes an original post (hook, caption, hashtags, slide/scene
   outline, visual direction, CTA) based on those stats.
5. **When to post and what to aim for.** Your next best posting slot, plus a target (top 25%) and a stretch
   goal (top 10%) for each metric.

It runs as one small Python server and a web app. On **PC** you open it in the browser. On **Android**
you open the same URL on the same Wi-Fi network and use *Add to Home screen* so it works like an app.
Reports are saved, so you can review past analyses on either device.

## Quick start (demo mode, no accounts needed)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
python run.py
```

Open the **PC** URL it prints. On your phone, open the **Phone** URL. If other people share your
network, set `APP_TOKEN` in `.env` and enter that token in the app's ⚙ settings.

Demo mode uses synthetic posts and a canned AI so you can try the whole flow. Switch to real data
and a real AI by editing `.env` as described below.

## Choosing a data source (`DATA_PROVIDER`)

| Option | Cost | Data you get | Risk |
|---|---|---|---|
| `apify` **(recommended)** | Pay per result (roughly a few dollars per 1,000 posts; the free plan includes monthly credit) | Full 60-day history per hashtag, with likes, comments and views | Scraping runs on Apify's servers, so your own IG account is never involved |
| `graph`: official Instagram Graph API | Free | Each hashtag's current top posts plus the last 24 hours of recent posts. Max 30 unique hashtags per 7 days. Needs a Business/Creator account linked to a Facebook Page | None, because it's within Instagram's terms. History builds up only as you keep running it |
| `mock` | Free | Synthetic | None |

Running your own scraper from your account (e.g. Instaloader) isn't included. It breaks often, and
Instagram rate-limits and bans accounts that do it.

A run with `apify` fetches up to `MAX_HASHTAGS` × `APIFY_RESULTS_PER_TAG` posts (8 × 150 by default).
Lower either one to spend less. Check Apify's current pricing before your first real run.

## Choosing the AI (`LLM_*`)

Any OpenAI-compatible API works. Set `LLM_PROVIDER=openai` and pick one:

| Provider | `LLM_BASE_URL` | `LLM_MODEL` | Notes |
|---|---|---|---|
| DeepSeek (default) | `https://api.deepseek.com` | `deepseek-chat` | Paid but very cheap; a run is a few thousand tokens |
| OpenRouter | `https://openrouter.ai/api/v1` | any listed model | One key for many models, some of them free (rate-limited) |
| Groq | `https://api.groq.com/openai/v1` | e.g. `llama-3.3-70b-versatile` | Free tier, very fast |
| Ollama (local, free) | `http://localhost:11434/v1` | e.g. `qwen2.5:14b` | Runs on your PC; needs a decent GPU; any non-empty `LLM_API_KEY` |
| Anthropic / OpenAI / Gemini | provider's OpenAI-compatible endpoint | | Stronger copywriting, higher cost |

The AI never produces the numbers. Timing, goals and benchmarks are computed in `backend/analysis.py`,
so a cheaper model can't make them up.

## How to read the results

- **Goals** are benchmarks taken from posts that are already ranking. Those mostly come from large
  accounts. If your account is small, treat "typical" as the realistic target and work up.
- **Best time** reflects when top posts were *published*. It's a strong hint, not proof of causation.
- **Hashtag samples skew toward top posts.** All sources return mostly well-performing posts, which
  suits "what works" analysis but overstates the averages.

## Project layout

```
backend/
  main.py          HTTP API + serves the web app
  pipeline.py      plan → collect → analyze → draft, run as background jobs
  agents.py        the two AI agents (search planner, post drafter)
  analysis.py      all statistics: windows, timing, goals, momentum
  llm.py           OpenAI-compatible client (+ offline mock)
  storage.py       SQLite cache of posts and reports (data/social_climb.db)
  providers/       apify.py, graph_api.py, mock.py
web/               installable web app (PWA)
tests/             pytest suite: python -m pytest
```

## Ideas for next steps

- Enter your follower count so goals scale to your account size.
- Scheduled background refreshes, so the history builds up even without pressing the button.
- Look up the accounts behind top posts to measure engagement *rate*, not just raw counts.
- Package as a native Android app (Capacitor) and Windows app (Tauri) wrapping the same web UI,
  with the server hosted in the cloud so the phone works away from home Wi-Fi.
