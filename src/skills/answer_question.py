from railtracks import function_node

from src.agent.context import SharedContext

# This will be set at app startup to the shared context instance
_shared_context: SharedContext | None = None


def set_shared_context(ctx: SharedContext) -> None:
    global _shared_context
    _shared_context = ctx


@function_node
def answer_question(question: str) -> str:
    """Look up information from recent observations and last-seen items to answer a question about the patient's environment, activities, or item locations."""
    if _shared_context is None:
        return "No observation context available."
    summary = _shared_context.get_summary()
    return f"Here is the current context to help answer '{question}':\n\n{summary}"
