"""Async client for the Trello MCP server used by the content bot."""

from __future__ import annotations

import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRELLO_PACKAGE = "@delorenj/mcp-server-trello"


class TrelloMCPError(RuntimeError):
    """Raised when the Trello MCP client cannot be configured or used."""


class TrelloMCPClient:
    """Connect to Trello MCP over stdio and expose its tools to the app."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    def _server_parameters(self) -> StdioServerParameters:
        load_dotenv(self.project_root / ".env")

        api_key = os.getenv("TRELLO_API_KEY")
        token = os.getenv("TRELLO_TOKEN")
        missing = [
            name
            for name, value in (
                ("TRELLO_API_KEY", api_key),
                ("TRELLO_TOKEN", token),
            )
            if not value
        ]
        if missing:
            names = ", ".join(missing)
            raise TrelloMCPError(
                f"Missing Trello configuration: {names}. "
                f"Add them to {self.project_root / '.env'}."
            )

        trello_env = {
            "TRELLO_API_KEY": api_key,
            "TRELLO_TOKEN": token,
        }
        for name in (
            "TRELLO_BOARD_ID",
            "TRELLO_WORKSPACE_ID",
            "TRELLO_ALLOWED_WORKSPACES",
        ):
            value = os.getenv(name)
            if value:
                trello_env[name] = value

        return StdioServerParameters(
            command=os.getenv("TRELLO_MCP_COMMAND", "npx"),
            args=["-y", TRELLO_PACKAGE],
            env=trello_env,
            cwd=self.project_root,
        )

    async def __aenter__(self) -> "TrelloMCPClient":
        self._exit_stack = AsyncExitStack()
        try:
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(self._server_parameters())
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
        except Exception:
            await self.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self._session = None
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None

    def _connected_session(self) -> ClientSession:
        if self._session is None:
            raise TrelloMCPError(
                "TrelloMCPClient is not connected; use it with 'async with'."
            )
        return self._session

    async def list_tools(self) -> list[Any]:
        """Return the tools exposed by the installed Trello MCP server."""

        result = await self._connected_session().list_tools()
        return list(result.tools)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call any Trello MCP tool by name."""

        return await self._connected_session().call_tool(name, arguments or {})

    async def list_boards(self) -> Any:
        """Return boards available to the configured Trello token."""

        return await self.call_tool("list_boards")

    async def get_lists(self, board_id: str | None = None) -> Any:
        """Return lists for a board, using the configured default when omitted."""

        arguments = {"boardId": board_id} if board_id else {}
        return await self.call_tool("get_lists", arguments)
