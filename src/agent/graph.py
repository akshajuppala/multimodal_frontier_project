import logging

import railtracks as rt

from src.agent.context import SharedContext
from src.agent.prompts import AGENT_SYSTEM_PROMPT
from src.logging.logger import AgentLogger
from src.skills.answer_question import answer_question, set_shared_context
from src.skills.calendar_read import calendar_read
from src.skills.calendar_write import calendar_write
from src.skills.call_emergency import call_emergency
from src.skills.medication import medication_check
from src.skills.routine import daily_routine
from src.skills.weather import weather_check
from src.skills.speech import speech_tool

logger = logging.getLogger(__name__)

ALL_TOOLS = [
    calendar_read,
    calendar_write,
    answer_question,
    call_emergency,
    medication_check,
    daily_routine,
    weather_check,
    speech_tool,
]


class MainAgent:
    def __init__(self, shared_context: SharedContext, agent_logger: AgentLogger):
        self._context = shared_context
        self._logger = agent_logger

        set_shared_context(shared_context)

        self._agent = rt.agent_node(
            name="Caregiver Assistant",
            llm=rt.llm.AnthropicLLM("claude-sonnet-4-20250514"),
            system_message=AGENT_SYSTEM_PROMPT.format(context_summary=""),
            tool_nodes=ALL_TOOLS,
        )

        self._flow = rt.Flow(
            "alzheimer-caregiver",
            entry_point=self._agent,
            save_state=True,
        )

    def _build_context_message(self) -> str:
        return self._context.get_summary()

    async def handle_speech(self, text: str) -> str:
        """Handle a user speech input and return the agent response."""
        context_summary = self._build_context_message()

        prompt = text
        if context_summary and context_summary != "No observations yet.":
            prompt = f"[Current context: {context_summary}]\n\nUser says: {text}"

        try:
            response = await self._flow.ainvoke(prompt)
            result = response.text if response and response.text else "I'm sorry, I couldn't process that."
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            result = "I'm sorry, something went wrong. Could you try asking again?"

        self._logger.log(
            trigger="speech",
            input_text=text,
            tool_calls=[],
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)

    async def handle_proactive(self, observation_summary: str) -> str:
        """Handle a proactive trigger from an urgent observation."""
        context_summary = self._build_context_message()

        prompt = (
            f"[Current context: {context_summary}]\n\n"
            f"URGENT OBSERVATION: {observation_summary}\n\n"
            "Assess this situation and take appropriate action. "
            "If this is a genuine emergency, call the emergency contact."
        )

        try:
            response = await self._flow.ainvoke(prompt)
            result = response.text if response and response.text else ""
        except Exception as e:
            logger.error(f"Proactive agent invocation failed: {e}")
            result = ""

        self._logger.log(
            trigger="proactive",
            input_text=observation_summary,
            tool_calls=[],
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)
