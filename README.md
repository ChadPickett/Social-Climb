# Social Climb

Pick a topic, hit **Analyze**, and get:

1. **Search plan.** An AI agent turns the topic into Instagram hashtags to research.
2. **Data collection.** Posts for those hashtags from the last 60 days are pulled and cached locally.
3. **Analysis.** Code (not the AI) computes the stats for the 7 / 15 / 30 / 60-day windows: typical vs. top
   likes, comments and views, best format, best weekdays and hours in *your* time zone, caption length,
   the hashtags top performers use, and whether the topic is heating up or cooling down.
4. **Patterns.** An AI agent looks at a sample of top posts (at most 2 per account) and lists the
   themes and hook styles that work. Code then drops any theme that only one account used, so a
   single viral creator can't steer the result.
   **Ideas.** A second AI agent writes 3 different, original post ideas built on those themes and on
   what you tell it about yourself and the photos/videos you have. It never sees other people's full
   captions, and code rejects any "Part 2"-style sequel of someone else's series.
5. **When to post and what to aim for.** Your next best posting slot, plus a target (top 25%) and a stretch
   goal (top 10%) for each metric.

It's one Windows program that opens in your browser, and your Android phone connects to it over your
Wi-Fi with a QR code. Reports are saved, so you can review past analyses on either device.

## Install (Windows)

1. Download **[SocialClimb.exe](https://github.com/chadpickett/social-climb/releases/latest/download/SocialClimb.exe)**.
2. Double-click it. If Windows says *"Windows protected your PC"*, click **More info → Run anyway**.
   (Windows shows this for any app from a small developer that hasn't paid for a signing certificate.)
   If Windows asks whether to allow it on networks, click **Allow** so your phone can connect.
3. The app opens in your browser. Type a topic and hit **Analyze** to try it with demo data.
4. To use real Instagram data, click **Open Settings** in the app and paste your two keys.
   The Settings screen links to where you get each one.
5. **Phone:** scan the QR code shown in the app with your phone's camera (same Wi-Fi as the PC),
   then use Chrome's ⋮ menu → **Add to Home screen**.

**Updates:** when a new version is out, the app shows an **Update now** button. It downloads,
verifies and installs the new version and restarts by itself. Your keys and reports are kept.

A black window stays open while the app runs. Close it to stop the app. Your keys, reports and
collected posts are saved in `%LOCALAPPDATA%\SocialClimb`.

## For developers

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py            # opens the app in your browser
python -m pytest         # tests
./build.sh               # package into dist/SocialClimb(.exe); needs `pip install pyinstaller`
```

Every push to `main` or the development branch builds the Windows `.exe` on GitHub Actions and
publishes it as the latest release. Settings can also come from environment variables or a `.env`
file (see `.env.example`). Values saved in the app's Settings screen take priority.

## Choosing a data source (`DATA_PROVIDER`)

| `DATA_PROVIDER` | Cost | Data you get | Risk |
|---|---|---|---|
| `apify` **(recommended)** | Pay per result (roughly a few dollars per 1,000 posts; the free plan includes monthly credit) | Full 60-day history per hashtag, with likes, comments and views | Scraping runs on Apify's servers, so your own IG account is never involved |
| `graph`: official Instagram Graph API | Free | Each hashtag's current top posts plus the last 24 hours of recent posts. Max 30 unique hashtags per 7 days. Needs a Business/Creator account linked to a Facebook Page | None, because it's within Instagram's terms. History builds up only as you keep running it |
| `mock` | Free | Synthetic | None |

Running your own scraper from your account (e.g. Instaloader) isn't included. It breaks often, and
Instagram rate-limits and bans accounts that do it.

The app uses Apify automatically once its key is in Settings. Each run collects up to
*hashtags × posts per hashtag* posts (8 × 50 by default; both adjustable under Settings → Advanced).
Check Apify's current pricing before your first real run. The official API needs `DATA_PROVIDER=graph`
plus `IG_GRAPH_TOKEN` and `IG_USER_ID` in `.env`.

## Choosing the AI (`LLM_*`)

DeepSeek is the default: paste its key in Settings and you're done. Any OpenAI-compatible API works
(change the address and model under Settings → Advanced):

| Provider | AI service address | AI model | Notes |
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
  agents.py        AI agents (search planner, pattern analyst, idea writer) + their guard rails
  analysis.py      all statistics: windows, timing, goals, momentum
  llm.py           OpenAI-compatible client (+ offline mock)
  storage.py       SQLite cache of posts and reports
  config.py        settings: defaults < env/.env < saved from the Settings screen
  providers/       apify.py, graph_api.py, mock.py
web/               installable web app (PWA)
tests/             pytest suite: python -m pytest
```

## Ideas for next steps

- Enter your follower count so goals scale to your account size.
- Scheduled background refreshes, so the history builds up even without pressing the button.
- Look up the accounts behind top posts to measure engagement *rate*, not just raw counts.
- Host the server online so the phone works away from home Wi-Fi and the PC can be off.
- A Mac build (same `build.sh`, run on a Mac runner).
