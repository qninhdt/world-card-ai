"""Language utilities for AI agent prompts."""

from __future__ import annotations

LANGUAGE_MAP = {
    "en": "English",
    "vi": "Vietnamese (Tiếng Việt)",
}


def language_instruction(lang_code: str) -> str:
    """Return language instruction for AI prompts.

    CRITICAL: All internal identifiers (tags, IDs, stat_check keys, node IDs,
    event IDs) MUST always be in English regardless of language setting.
    Only user-facing display text should be in the target language.
    """
    lang_name = LANGUAGE_MAP.get(lang_code, "English")
    if lang_code == "en":
        return "Write all text in English."

    return (
        f"Write all USER-FACING text (names, descriptions, dialog, flavor text) "
        f"in {lang_name}.\n"
        f"CRITICAL: All INTERNAL identifiers must remain in English:\n"
        f"- Tags (e.g. 'war_declared', not 'chiến_tranh')\n"
        f"- IDs (e.g. 'border_crisis', not 'khủng_hoảng')\n"
        f"- Stat check keys\n"
        f"- Event IDs\n"
        f"- chain_tag values"
    )
