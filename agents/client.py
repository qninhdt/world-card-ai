from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_heavy_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("HEAVY_MODEL", "google/gemini-2.5-pro"),
        api_key=os.getenv("OPENROUTER_API_KEY", "sk-placeholder"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.9,
        max_tokens=32768,
    )


def get_fast_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("FAST_MODEL", "google/gemini-2.5-flash"),
        api_key=os.getenv("OPENROUTER_API_KEY", "sk-placeholder"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=32768,
    )
