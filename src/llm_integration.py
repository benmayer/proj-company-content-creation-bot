"""The only module that calls the LLM API.

Configuration comes from the environment (or a local ``.env``): ``OPENAI_API_KEY``
and ``LLM_MODEL``. Callers pass a rendered prompt string and get draft text back;
every failure surfaces as an ``LLMError`` whose message says what to fix.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

import openai
from dotenv import load_dotenv
from openai import OpenAI

API_KEY_VAR = "OPENAI_API_KEY"
MODEL_VAR = "LLM_MODEL"


class LLMError(RuntimeError):
    """Any failure to obtain a draft from the model."""


class LLMConfigError(LLMError):
    """Required configuration is missing or empty."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(repr=False)
    model: str


def load_config() -> LLMConfig:
    """Read the API key and model name from the environment, loading ``.env`` first."""
    load_dotenv()
    values = {name: os.environ.get(name, "").strip() for name in (API_KEY_VAR, MODEL_VAR)}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise LLMConfigError(
            f"Missing {', '.join(missing)}. Copy .env.example to .env and set it "
            "(or set it as an environment variable)."
        )
    return LLMConfig(api_key=values[API_KEY_VAR], model=values[MODEL_VAR])


def generate_draft(prompt: str, client: Optional[OpenAI] = None) -> str:
    """Send a rendered prompt to the configured model and return the draft text.

    ``client`` is injectable so tests can run without network access or a key.
    """
    if not prompt or not prompt.strip():
        raise LLMError("Cannot generate a draft from an empty prompt.")

    config = load_config()
    client = client or OpenAI(api_key=config.api_key)

    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": prompt}],
        )
    except openai.AuthenticationError as exc:
        raise LLMError(f"The API rejected {API_KEY_VAR} (401). Check the key in .env.") from exc
    except openai.NotFoundError as exc:
        raise LLMError(
            f"Model '{config.model}' was not found or is not available to this key (404). "
            f"Check {MODEL_VAR} in .env."
        ) from exc
    except openai.RateLimitError as exc:
        raise LLMError("Rate limit or quota exceeded (429). Wait and retry, or check billing.") from exc
    except openai.APIConnectionError as exc:
        raise LLMError("Could not reach the OpenAI API. Check the network connection and retry.") from exc
    except openai.APIStatusError as exc:
        raise LLMError(f"The OpenAI API returned an error (HTTP {exc.status_code}): {exc.message}") from exc

    text = response.choices[0].message.content if response.choices else None
    if not text or not text.strip():
        raise LLMError("The model returned an empty response. Retry, or adjust the prompt.")
    return text.strip()
