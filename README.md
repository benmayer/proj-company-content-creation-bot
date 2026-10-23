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
