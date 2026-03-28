import railtracks as rt

from src.agent.context import SharedContext

_shared_context: SharedContext | None = None


def set_shared_context(ctx: SharedContext) -> None:
    global _shared_context
    _shared_context = ctx


@rt.function_node
def answer_question(question: str) -> str:
    """Look up information from recent observations and last-seen items to answer a question about the patient's environment, activities, or item locations.

    Args:
        question (str): The user's question about their environment, items, or activities.
    """
    if _shared_context is None:
        return "No observation context available."
    summary = _shared_context.get_summary()
    return f"Here is the current context to help answer '{question}':\n\n{summary}"
