"""Writer agent — generates weekly card batches using a fast LLM.

The Writer receives:
- The world context and available stat names
- A ``common_count`` indicating how many regular cards to generate
- A list of ``CardGenJob`` objects for special cards (plot, event, etc.)
- A context dict with the current game snapshot, DAG state, ongoing events,
  and season info

It renders Jinja2 prompt templates, calls the fast model, repairs the JSON
response (tolerating minor malformations), and validates the output against
``WriterBatchOutput``.

All card routing (structural vs. deck cards) is handled by the engine's
``process_batch_output()`` method — the Writer only produces raw definitions.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agents.client import get_fast_model
from agents.language import language_instruction
from agents.prompt_loader import render
from agents.schemas import CardDef, WriterBatchOutput
from game.cost import CostTracker
from game.job_queue import CardGenJob
import json_repair
import re
from langchain_core.output_parsers import PydanticOutputParser

class Writer:
    """Generates a batch of cards for one game week using the fast LLM model.

    Instantiated fresh each week so the world context and stat names are
    always up-to-date.
    """

    def __init__(
        self,
        world_context: str = "",
        stat_names: list[str] | None = None,
        cost_tracker: CostTracker | None = None,
        language: str = "en",
    ) -> None:
        self.model = get_fast_model()
        self.chain = self.model
        self.world_context = world_context
        self.stat_names = stat_names or []
        self.cost_tracker = cost_tracker
        self.language = language

    async def generate_batch(
        self,
        common_count: int,
        jobs: list[CardGenJob],
        context: dict,
    ) -> WriterBatchOutput:
        """Generate ``common_count`` common cards plus one card per job.

        Returns a ``WriterBatchOutput`` containing all generated card defs.
        JSON repair is attempted on malformed model output before validation.
        """
        lang_note = language_instruction(self.language)

        system_prompt = render("writer_system.j2")
        user_prompt = render(
            "writer_user.j2",
            language_instruction=lang_note,
            world_context=self.world_context,
            stat_names=self.stat_names,
            is_season_start=context.get("is_season_start", False),
            is_first_day_after_death=context.get("is_first_day_after_death", False),
            elapsed_days=context.get("snapshot", {}).get("elapsed_days", 0),
            life_number=context.get("snapshot", {}).get("life", 1),
            snapshot=context.get("snapshot", {}),
            dag_context=context.get("dag_context", {}),
            ongoing_events=context.get("ongoing_events", []),
            available_tags=context.get("available_tags", []),
            season=context.get("season", {"name": "", "description": "", "week": 1}),
            common_count=common_count,
            jobs=jobs,
        )

        parser = PydanticOutputParser(pydantic_object=WriterBatchOutput)
        user_prompt += f"\n\nOUTPUT FORMAT REQUIREMENTS:\n{parser.get_format_instructions()}\n\nNote: Return ONLY the JSON object, wrapped in ```json ... ``` fences. Pay close attention to the required field names like 'title' (NOT 'name')."

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        result = await self.chain.ainvoke(messages)
        
        # Extract JSON from markdown fences if present
        raw_content = result.content
        json_match = re.search(r'```(?:json)?\s*\n(.*?)```', raw_content, re.DOTALL)
        json_str = json_match.group(1).strip() if json_match else raw_content.strip()
        
        # Repair and parse JSON gracefully
        repaired_dict = json_repair.repair_json(json_str, return_objects=True)
        parsed = WriterBatchOutput.model_validate(repaired_dict)
        
        if self.cost_tracker:
            self.cost_tracker.record_from_raw(result, label="Writer")
        return parsed
