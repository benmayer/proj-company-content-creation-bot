# proj-company-content-creation-bot
A small product that creates public company posts, including the tone of voice and company knowledgebase

## Local UI

The local front end uses Streamlit and keeps the request form beside the draft
review panel. Each channel offers its own content types:

| Channel | Types |
|---|---|
| LinkedIn | regular post, press release |
| Instagram | regular post, reply to post, meme |
| X | regular post, reply to post, meme |
| internal Slack | press release (internal), regular post, meme |

The voice rules for each channel and type, and real past examples, live as Markdown
in `knowledge_base/primary/` (see [its README](knowledge_base/README.md)); edits apply
on the next draft without a restart.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Set `OPENAI_API_KEY` and `LLM_MODEL` in `.env` first. Every type needs only a topic,
except **reply to post**: paste the post's text, upload a screenshot of it, or both.
Links are not opened, so a link on its own is refused. Nothing is saved until
**Approve + save** is selected. Screenshots stay in memory and are not committed.

**Model:** `evidence/voice_check.py` drafts the same 12 requests through the pipeline
and through a generic one-line prompt, and writes `evidence/voice/comparison_<model>.md`.
On those runs `gpt-5.4-mini` followed the rules better than `gpt-4o-mini` (no invented
facts in the press release, sharper replies), so we recommend `LLM_MODEL=gpt-5.4-mini`.
Third-party price lists give $0.75 per million input and $4.50 per million output tokens
for it (check OpenAI's pricing page); a draft is about 3,000 input tokens, so roughly
$0.003 per draft before screenshots.

The command-line entry point can be run from the project directory with:

```bash
.venv/bin/python -m src.main --content-type post --topic "a weekend getaway" --channel Instagram
.venv/bin/python -m src.main --content-type reply --channel X --screenshot post.png
```

Running `src/main.py` directly from an IDE is also supported.

## Deploy to Render

The UI runs as a Render web service defined by [`render.yaml`](render.yaml)
(Python 3.12, `streamlit run app.py` bound to `$PORT`). No `.env` is needed there.

1. In Render, choose **New → Blueprint** and select this repo. Render reads `render.yaml`.
2. Set the three variables marked `sync: false` in the service's **Environment** tab:

   | Variable | Value |
   |---|---|
   | `OPENAI_API_KEY` | your OpenAI key |
   | `LLM_MODEL` | model name to call |
   | `APP_PASSWORD` | shared password for the team |

3. Deploy. The app asks for `APP_PASSWORD` before showing anything; if the variable
   is missing on Render it stays locked, so the API quota cannot be spent by outsiders.

**Free-tier cold start:** the free plan spins the service down after ~15 minutes
without traffic, and the first request afterwards takes about a minute to wake it.

**Persistence:** we stay on the free plan, whose disk is ephemeral. Approved drafts in
`outputs/` and the learned feedback in `outputs/feedback.jsonl` are lost on every
redeploy or restart, so the self-learning does not persist on Render. To keep them,
use a paid instance with a disk mounted at `/var/data` and set
`FEEDBACK_STORE_PATH=/var/data/feedback.jsonl`.

**Live URL:** https://proj-company-content-creation-bot.onrender.com

## Trello MCP connection

The app connects to `@delorenj/mcp-server-trello` through the Python MCP SDK.
Keep `TRELLO_API_KEY` and `TRELLO_TOKEN` in the local `.env` file; never commit
that file.

Install dependencies, then use the client from an async workflow:

```python
from src.trello_mcp import TrelloMCPClient

async with TrelloMCPClient() as trello:
    boards = await trello.list_boards()
```

The client launches the MCP server with `npx`, so Node.js/npm must be installed
on the machine running the app.
