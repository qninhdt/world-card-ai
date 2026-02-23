"""API cost tracking across all LLM calls in a session.

``CostTracker`` accumulates ``CostEntry`` records from two sources:
  - ``record_from_raw()`` — parses cost/token data from a LangChain
    ``AIMessage``'s metadata (works for non-streaming calls).
  - ``record_manual()`` — estimates token counts from character lengths
    (used for streaming calls where metadata is not available per-chunk).

The ``summary`` and ``detail`` properties format totals for display in the
``CostDisplay`` widget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CostEntry:
    label: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    model: str = ""


class CostTracker:
    """Tracks cumulative API costs across all LLM calls."""

    def __init__(self) -> None:
        self.entries: list[CostEntry] = []
        self.total_cost: float = 0.0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0

    def record_from_raw(self, raw_message: Any, label: str = "") -> CostEntry:
        """Extract cost info from a LangChain AIMessage's response_metadata."""
        meta = getattr(raw_message, "response_metadata", {}) or {}
        usage = getattr(raw_message, "usage_metadata", {}) or {}

        # usage_metadata has input_tokens / output_tokens (LangChain standard)
        prompt_tokens = (
            usage.get("input_tokens", 0)
            or meta.get("token_usage", {}).get("prompt_tokens", 0)
        )
        completion_tokens = (
            usage.get("output_tokens", 0)
            or meta.get("token_usage", {}).get("completion_tokens", 0)
        )
        total_tokens = prompt_tokens + completion_tokens
        model = meta.get("model_name", "") or meta.get("model", "")

        cost = self._extract_cost(meta)

        entry = CostEntry(
            label=label,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            model=model,
        )
        self.entries.append(entry)
        self.total_cost += cost
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        return entry

    @staticmethod
    def _extract_cost(meta: dict) -> float:
        """OpenRouter puts `cost` inside the token_usage dict (from CompletionUsage).
        Also try several fallback locations."""
        # Primary: OpenRouter adds `cost` to the CompletionUsage object,
        # which LangChain stores at response_metadata["token_usage"]["cost"]
        token_usage = meta.get("token_usage") or {}
        if isinstance(token_usage, dict):
            val = token_usage.get("cost")
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass

        # Fallback: top-level cost key
        for key in ("cost", "openrouter_cost", "x-openrouter-cost"):
            val = meta.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    pass

        # Fallback: HTTP response headers forwarded by LangChain
        headers = meta.get("headers") or {}
        if isinstance(headers, dict):
            for key in ("x-openrouter-cost", "X-Openrouter-Cost"):
                val = headers.get(key)
                if val is not None:
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        pass

        return 0.0

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    @property
    def summary(self) -> str:
        if not self.entries:
            return "$0.00"
        return f"${self.total_cost:.4f}"

    @property
    def detail(self) -> str:
        lines = [f"Total: ${self.total_cost:.4f}  ({self.total_tokens} tokens)"]
        for e in self.entries:
            cost_str = f"${e.cost:.4f}" if e.cost > 0 else "?"
            lines.append(f"  {e.label}: {cost_str} ({e.total_tokens} tok)")
        return "\n".join(lines)

    def record_manual(
        self,
        input_chars: int = 0,
        output_chars: int = 0,
        label: str = "",
    ) -> CostEntry:
        """Record an approximate cost entry for streaming calls (no metadata)."""
        # Rough estimate: ~4 chars per token
        prompt_tokens = input_chars // 4
        completion_tokens = output_chars // 4
        entry = CostEntry(
            label=label,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model="streaming",
        )
        self.entries.append(entry)
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        return entry

    def reset(self) -> None:
        self.entries.clear()
        self.total_cost = 0.0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
