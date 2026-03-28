import logging

from railtracks import agent_node, call, Flow, function_node
from railtracks.llm import AnthropicLLM

from src.agent.context import SharedContext
from src.agent.prompts import AGENT_SYSTEM_PROMPT
from src.config import settings
from src.logging.logger import AgentLogger
from src.skills.answer_question import answer_question, set_shared_context
from src.skills.calendar_read import calendar_read
from src.skills.calendar_write import calendar_write
from src.skills.call_emergency import call_emergency

logger = logging.getLogger(__name__)


class MainAgent:
    def __init__(self, shared_context: SharedContext, agent_logger: AgentLogger):
        self._context = shared_context
        self._logger = agent_logger

        set_shared_context(shared_context)

        self._llm = AnthropicLLM(
            model_name="claude-sonnet-4-20250514",
            temperature=0,
            api_key=settings.anthropic_api_key,
        )

        self._tools = [calendar_read, calendar_write, answer_question, call_emergency]

    def _build_agent(self, system_msg: str):
        """Build a fresh agent node with the current system message."""
        return agent_node(
            name="caregiver_assistant",
            llm=self._llm,
            tool_nodes=self._tools,
            system_message=system_msg,
        )

    async def handle_speech(self, text: str) -> str:
        """Handle a user speech input and return the agent response."""
        system_msg = AGENT_SYSTEM_PROMPT.format(
            context_summary=self._context.get_summary()
        )

        Agent = self._build_agent(system_msg)

        @function_node
        async def speech_flow(user_input: str) -> str:
            return await call(Agent, user_input)

        flow = Flow("speech", speech_flow)
        result = await flow.ainvoke(text)

        response_text = result if isinstance(result, str) else str(result)

        await self._context.add_conversation_async(text, response_text)

        self._logger.log(
            trigger="speech",
            input_text=text,
            tool_calls=[],
            response=response_text,
        )

        return response_text

    async def handle_proactive(self, observation_summary: str) -> str:
        """Handle a proactive trigger from an urgent observation."""
        system_msg = AGENT_SYSTEM_PROMPT.format(
            context_summary=self._context.get_summary()
        )

        Agent = self._build_agent(system_msg)

        prompt = (
            f"URGENT OBSERVATION: {observation_summary}\n\n"
            "Assess this situation and take appropriate action. "
            "If this is a genuine emergency, call the emergency contact."
        )

        @function_node
        async def proactive_flow(user_input: str) -> str:
            return await call(Agent, user_input)

        flow = Flow("proactive", proactive_flow)
        result = await flow.ainvoke(prompt)

        self._logger.log(
            trigger="proactive",
            input_text=observation_summary,
            tool_calls=[],
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)
