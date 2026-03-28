"""
LangGraph orchestrator — single-agent graph with tool-calling.

One LLM node that has full context (current state, conversation history)
and can call any of the registered tools. The graph loops:
    agent -> tools -> agent  until the agent stops calling tools.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from server.tools import (
    analyze_frame,
    answer_question,
    calendar_read,
    calendar_write,
    daily_routine,
    get_previous_state,
    medication_check,
    speech_tool,
    weather_check,
)

MAIN_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "main_agent_system.md"

ALL_TOOLS = [
    analyze_frame,
    calendar_read,
    calendar_write,
    answer_question,
    get_previous_state,
    speech_tool,
    medication_check,
    daily_routine,
    weather_check,
]


class GraphState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def _load_system_prompt() -> str:
    return MAIN_PROMPT_PATH.read_text()


def _make_agent_node(model_name: str = "gpt-4o"):
    llm = ChatOpenAI(model=model_name, temperature=0.3).bind_tools(ALL_TOOLS)
    system_prompt = _load_system_prompt()

    def agent(state: GraphState) -> dict:
        messages = state["messages"]

        # Inject system prompt if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)

        response = llm.invoke(messages)
        return {"messages": [response]}

    return agent


def _should_continue(state: GraphState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


def build_graph(model_name: str = "gpt-4o") -> StateGraph:
    """Build and compile the LangGraph agent graph.

    Returns a compiled graph ready to invoke with:
        graph.invoke({"messages": [HumanMessage(content="...")]})
    """
    agent_node = _make_agent_node(model_name)
    tool_node = ToolNode(ALL_TOOLS)

    graph = StateGraph(GraphState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")

    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def create_frame_message(frame_base64: str) -> HumanMessage:
    """Create a message for the agent when a new frame arrives.

    The agent will decide whether to analyze the frame with the
    analyze_frame tool based on its judgment.
    """
    return HumanMessage(
        content=(
            "A new camera frame has arrived. Assess whether enough time has passed "
            "or if something appears to have changed that warrants analysis. "
            "If so, use the analyze_frame tool. The frame data (base64): "
            f"{frame_base64[:100]}... [truncated — pass full string to analyze_frame]"
        ),
        additional_kwargs={"frame_base64": frame_base64},
    )


def create_question_message(text: str) -> HumanMessage:
    """Create a message for the agent when the user asks a question."""
    return HumanMessage(content=text)


def create_observation_alert(observation: dict) -> HumanMessage:
    """Create a message when the frame analysis returns an actionable observation.

    This feeds the observation back to the agent so it can decide
    whether to speak, remind, or escalate.
    """
    import json

    return HumanMessage(
        content=(
            "Frame analysis complete. Here are the observations:\n"
            f"```json\n{json.dumps(observation, indent=2)}\n```\n"
            "Decide if you need to take any action (speak to the user, check calendar, "
            "log routine, etc). If nothing needs action, do nothing."
        )
    )
