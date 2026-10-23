# proj-company-content-creation-bot
A small product that creates public company posts, including the tone of voice and company knowledgebase

## Local UI

The local front end uses Streamlit and keeps the request form beside the draft
review panel. It supports LinkedIn, Instagram, X, and internal Slack; reply,
press release, post update, and meme types; source-document visibility; feedback
iterations; and approval-gated saving to `outputs/`. Channel profiles are
derived from the primary brand-voice knowledge base, while content templates
remain composable across all four channels.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Set `OPENAI_API_KEY` in `.env` first. A reply only needs the original message;
the other types also need a product and topic. Nothing is saved until **Approve + save** is selected. Uploaded assets remain in
memory and are not committed.

The command-line entry point can be run from the project directory with:

```bash
.venv/bin/python -m src.main --content-type social_post --product flights \
  --topic "a weekend getaway" --channel Instagram
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

**Persistence:** TODO (decision pending, see card 20).

**Live URL:** TODO (set after the first deploy).

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
