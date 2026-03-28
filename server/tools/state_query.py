"""
State query tools — search the observation history and object memory
to answer user questions about items, people, and past events.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from server.state.store import StateStore


@tool
def answer_question(question: str) -> dict:
    """Search memory for information about objects, people, and past events.

    Use this when the user asks about a lost item, a person, or something
    that happened earlier. Searches both the object tracking state and
    the observation history.

    Args:
        question: The user's question (e.g., "Where are my keys?", "When did Sarah leave?").

    Returns:
        Answer with relevant sources and timestamps.
    """
    store = StateStore()
    try:
        results = {"object_matches": [], "people_matches": [], "observation_matches": []}

        keywords = _extract_keywords(question)

        for kw in keywords:
            objects = store.search_objects(kw)
            for obj in objects:
                results["object_matches"].append({
                    "item": obj.item,
                    "location": obj.location,
                    "last_seen": obj.last_seen.isoformat(),
                    "confidence": obj.confidence,
                })

            person = store.get_person_state(kw)
            if person:
                results["people_matches"].append({
                    "name": person.name,
                    "present": person.present,
                    "last_seen": person.last_seen.isoformat(),
                    "arrived_at": person.arrived_at.isoformat() if person.arrived_at else None,
                    "departed_at": person.departed_at.isoformat() if person.departed_at else None,
                })

            obs = store.search_observations(kw, limit=5)
            results["observation_matches"].extend(obs)

        # Deduplicate observations
        seen_ts = set()
        unique_obs = []
        for o in results["observation_matches"]:
            if o["timestamp"] not in seen_ts:
                seen_ts.add(o["timestamp"])
                unique_obs.append(o)
        results["observation_matches"] = unique_obs[:10]

        return results
    finally:
        store.close()


@tool
def get_previous_state(hours_back: float = 4.0) -> dict:
    """Retrieve historical observations and activity from the recent past.

    Use this for questions like "What did I do this morning?" or
    "What happened in the last hour?"

    Args:
        hours_back: How many hours of history to retrieve. Defaults to 4.

    Returns:
        List of observations and routine entries from the time range.
    """
    store = StateStore()
    try:
        now = datetime.utcnow()
        from_time = now - timedelta(hours=hours_back)

        observations = store.get_observations(from_time=from_time, to_time=now, limit=30)
        routine = store.get_routine_range(from_time, now)

        return {
            "time_range": {"from": from_time.isoformat(), "to": now.isoformat()},
            "observations": observations,
            "routine": [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "activity": r.activity,
                    "location": r.location,
                }
                for r in routine
            ],
        }
    finally:
        store.close()


# Common objects an Alzheimer's patient might ask about
_COMMON_ITEMS = {
    "keys", "wallet", "phone", "glasses", "remote", "purse", "bag",
    "medication", "pills", "medicine", "watch", "hearing aid", "cane",
    "umbrella", "jacket", "coat", "hat", "shoes", "slippers",
}

_QUESTION_STOP_WORDS = {
    "where", "are", "is", "my", "the", "have", "you", "seen", "did",
    "when", "was", "what", "who", "how", "do", "does", "can", "will",
    "i", "a", "an", "to", "in", "on", "at", "it", "of", "for", "with",
}


def _extract_keywords(question: str) -> list[str]:
    words = question.lower().replace("?", "").replace("!", "").replace(".", "").split()
    keywords = [w for w in words if w not in _QUESTION_STOP_WORDS and len(w) > 1]
    # Prioritize common items if they appear
    prioritized = [w for w in keywords if w in _COMMON_ITEMS]
    others = [w for w in keywords if w not in _COMMON_ITEMS]
    return prioritized + others if prioritized else keywords
