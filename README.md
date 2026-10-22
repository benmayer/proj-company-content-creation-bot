# proj-company-content-creation-bot
A small product that creates public company posts, including the tone of voice and company knowledgebase

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
