import json
from datetime import datetime, timezone
from pathlib import Path


class AgentLogger:
    def __init__(self, log_path: str = "data/agent_log.jsonl"):
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        trigger: str,
        input_text: str,
        tool_calls: list[dict],
        response: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "input": input_text,
            "tool_calls": tool_calls,
            "response": response,
        }
        print(entry)
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
