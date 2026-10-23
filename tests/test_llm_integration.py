"""Mocked-client checks for the LLM boundary: no network, no real key."""

import ast
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import httpx
import openai

from src import llm_integration
from src.llm_integration import LLMConfigError, LLMError, generate_draft, load_config

FAKE_KEY = "sk-test-not-a-real-key"
ENV = {"OPENAI_API_KEY": FAKE_KEY, "LLM_MODEL": "test-model"}
REQUEST = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _status_error(cls, status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=REQUEST)
    return cls("boom", response=response, body=None)


def _client(*, text=None, error=None) -> mock.Mock:
    client = mock.Mock()
    if error is not None:
        client.chat.completions.create.side_effect = error
    else:
        message = SimpleNamespace(content=text)
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )
    return client


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(llm_integration, "load_dotenv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_key_and_model_are_named(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LLMConfigError) as ctx:
                load_config()
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))
        self.assertIn("LLM_MODEL", str(ctx.exception))

    def test_blank_key_counts_as_missing(self) -> None:
        with mock.patch.dict(os.environ, {**ENV, "OPENAI_API_KEY": "  "}, clear=True):
            with self.assertRaises(LLMConfigError):
                load_config()

    def test_key_is_not_in_config_repr(self) -> None:
        with mock.patch.dict(os.environ, ENV, clear=True):
            self.assertNotIn(FAKE_KEY, repr(load_config()))


class GenerateDraftTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(llm_integration, "load_dotenv")
        patcher.start()
        self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_returns_stripped_text_and_uses_configured_model(self) -> None:
        client = _client(text="  Fares from €9.99.  ")
        self.assertEqual(generate_draft("Write a post", client=client), "Fares from €9.99.")
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "test-model")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "Write a post"}])

    def test_empty_prompt_is_rejected_before_any_call(self) -> None:
        client = _client(text="x")
        with self.assertRaises(LLMError):
            generate_draft("   ", client=client)
        client.chat.completions.create.assert_not_called()

    def test_failures_map_to_actionable_errors(self) -> None:
        cases = [
            (_status_error(openai.AuthenticationError, 401), "OPENAI_API_KEY"),
            (_status_error(openai.NotFoundError, 404), "LLM_MODEL"),
            (_status_error(openai.RateLimitError, 429), "429"),
            (openai.APIConnectionError(request=REQUEST), "network"),
            (_status_error(openai.InternalServerError, 500), "500"),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(LLMError) as ctx:
                    generate_draft("prompt", client=_client(error=error))
                self.assertIn(expected, str(ctx.exception))
                self.assertNotIn(FAKE_KEY, str(ctx.exception))

    def test_empty_model_response_is_an_error(self) -> None:
        with self.assertRaises(LLMError):
            generate_draft("prompt", client=_client(text=""))


class BoundaryTests(unittest.TestCase):
    def test_only_llm_integration_imports_the_provider(self) -> None:
        src = Path(__file__).resolve().parent.parent / "src"
        for path in src.glob("*.py"):
            if path.name == "llm_integration.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    self.assertNotEqual(name.split(".")[0], "openai", f"{path.name} imports openai")


if __name__ == "__main__":
    unittest.main()
