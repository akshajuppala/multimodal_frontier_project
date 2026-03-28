import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agent.context import SharedContext
from src.agent.prompts import AGENT_SYSTEM_PROMPT
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

        model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0,
        )

        self._tools = [calendar_read, calendar_write, answer_question, call_emergency]

        self._agent = create_react_agent(
            model=model,
            tools=self._tools,
        )

    def _build_system_message(self) -> str:
        return AGENT_SYSTEM_PROMPT.format(
            context_summary=self._context.get_summary()
        )

    async def handle_speech(self, text: str) -> str:
        """Handle a user speech input and return the agent response."""
        system_msg = self._build_system_message()

        response = await self._agent.ainvoke({
            "messages": [
                {"role": "system", "content": system_msg},
                HumanMessage(content=text),
            ]
        })

        # Extract the final assistant message
        ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
        result = ai_messages[-1].content if ai_messages else "I'm sorry, I couldn't process that."

        # Extract tool calls for logging
        tool_calls = []
        for m in response["messages"]:
            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({"name": tc["name"], "args": tc["args"]})

        self._logger.log(
            trigger="speech",
            input_text=text,
            tool_calls=tool_calls,
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)

    async def handle_proactive(self, observation_summary: str) -> str:
        """Handle a proactive trigger from an urgent observation."""
        system_msg = self._build_system_message()

        prompt = (
            f"URGENT OBSERVATION: {observation_summary}\n\n"
            "Assess this situation and take appropriate action. "
            "If this is a genuine emergency, call the emergency contact."
        )

        response = await self._agent.ainvoke({
            "messages": [
                {"role": "system", "content": system_msg},
                HumanMessage(content=prompt),
            ]
        })

        ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
        result = ai_messages[-1].content if ai_messages else ""

        tool_calls = []
        for m in response["messages"]:
            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({"name": tc["name"], "args": tc["args"]})

        self._logger.log(
            trigger="proactive",
            input_text=observation_summary,
            tool_calls=tool_calls,
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)
