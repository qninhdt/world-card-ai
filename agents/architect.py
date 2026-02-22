"""Streaming world generation — single LLM call, parses sections as they arrive.

The Architect outputs markdown like:
    # Creative Loading Title...
    ```json
    { ... section data ... }
    ```
    # Next Section Title...
    ```json
    { ... }
    ```

This module streams tokens, detects completed sections, and yields them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import AsyncIterator
import openai

import json_repair

from langchain_core.messages import HumanMessage, SystemMessage

from agents.client import get_heavy_model
from agents.language import language_instruction
from agents.prompt_loader import render
from agents.schemas import WorldGenSchema
from game.cost import CostTracker


SECTION_ORDER = [
    "world_core",
    "player_and_stats",
    "npcs_and_relationships",
    "tags",
    "story",
    "seasons",
]

TOTAL_SECTIONS = len(SECTION_ORDER)


@dataclass
class StreamSection:
    """A completed section from the stream."""

    index: int  # 0-based section number
    key: str  # "world_core", "stats", etc.
    title: str  # AI-generated heading text
    data: dict  # Parsed JSON


@dataclass
class _ParserState:
    """Accumulator for the streaming parser."""

    buffer: str = ""
    sections: list[StreamSection] = field(default_factory=list)
    _scan_pos: int = 0  # Position in buffer we've already parsed up to

    def feed(self, chunk: str) -> list[StreamSection]:
        """Feed a chunk of streamed text. Returns any newly completed sections."""
        self.buffer += chunk
        return self._try_parse()

    def finalize(self) -> list[StreamSection]:
        """Flush any remaining section in the buffer."""
        return self._try_parse()

    def _try_parse(self) -> list[StreamSection]:
        new_sections: list[StreamSection] = []

        # Pattern: # Title\n```json\n{...}\n```
        pattern = r"#\s*(.+?)\s*\n\s*```json\s*\n(.*?)```"

        for match in re.finditer(pattern, self.buffer[self._scan_pos:], re.DOTALL):
            title = match.group(1).strip()
            json_str = match.group(2).strip()
            section_idx = len(self.sections) + len(new_sections)

            try:
                data = json_repair.loads(json_str)
                key = SECTION_ORDER[section_idx] if section_idx < len(SECTION_ORDER) else f"extra_{section_idx}"
                section = StreamSection(
                    index=section_idx,
                    key=key,
                    title=title,
                    data=data,
                )
                new_sections.append(section)
                # Advance scan position past this match
                self._scan_pos += match.end()
            except (json.JSONDecodeError, IndexError):
                continue

        self.sections.extend(new_sections)
        return new_sections


def _assemble_world(sections: list[StreamSection]) -> WorldGenSchema:
    """Assemble completed sections into a WorldGenSchema."""
    if not sections:
        raise RuntimeError(
            "Architect returned no parseable sections. "
            "The LLM response may have been empty or malformed. "
            "Please retry."
        )
    merged: dict = {}
    for section in sections:
        merged.update(section.data)
    return WorldGenSchema(**merged)


async def stream_world(
    theme: str,
    stat_count: int,
    language: str = "en",
    cost_tracker: CostTracker | None = None,
) -> AsyncIterator[StreamSection | WorldGenSchema]:
    """Stream world generation, yielding sections as they complete.

    Yields:
        StreamSection — each time a section's JSON block is fully received
        WorldGenSchema — as the final yield, the assembled world
    """
    model = get_heavy_model()
    lang_note = language_instruction(language)

    system_prompt = render("architect_system.j2")
    user_prompt = render(
        "architect_user.j2",
        language_instruction=lang_note,
        theme=theme,
        stat_count=stat_count,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    parser = _ParserState()
    full_response = ""

    try:
        async for chunk in model.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if not token:
                continue
            full_response += token
            new_sections = parser.feed(token)
            for section in new_sections:
                yield section
    except openai.APIError as e:
        # Check if we got any sections at all before failing
        if not parser.sections:
            raise RuntimeError(f"Failed to generate world because the AI provider encountered an error: {e}")
        # Otherwise, if we got a partial stream, we'll just try to finalize what we have.

    # Finalize any remaining section
    remaining = parser.finalize()
    for section in remaining:
        yield section

    # Track cost if available
    if cost_tracker:
        # Approximate token count from response length
        cost_tracker.record_manual(
            input_chars=len(system_prompt) + len(user_prompt),
            output_chars=len(full_response),
            label="Architect (streaming)",
        )

    # Assemble and yield final WorldGenSchema
    yield _assemble_world(parser.sections)
