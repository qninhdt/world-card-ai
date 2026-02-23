from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

_API_KEY_PLACEHOLDER = "sk-placeholder"


def _get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY", _API_KEY_PLACEHOLDER)
    if key == _API_KEY_PLACEHOLDER:
        logger.warning(
            "OPENROUTER_API_KEY is not set. API calls will fail. "
            "Set the variable in your .env file or environment."
        )
    return key


def get_heavy_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("HEAVY_MODEL", "google/gemini-2.5-pro"),
        api_key=_get_api_key(),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.9,
        max_tokens=32768,
    )


def get_fast_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("FAST_MODEL", "google/gemini-2.5-flash"),
        api_key=_get_api_key(),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=32768,
    )
