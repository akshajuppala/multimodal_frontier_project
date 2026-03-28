import json
import tempfile
from pathlib import Path

from src.logging.logger import AgentLogger


def test_log_entry_appends_to_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        log_path = f.name

    logger = AgentLogger(log_path)
    logger.log(
        trigger="speech",
        input_text="where are my keys?",
        tool_calls=[],
        response="Your keys were last seen on the kitchen counter.",
    )

    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["trigger"] == "speech"
    assert entry["input"] == "where are my keys?"
    assert "timestamp" in entry

    Path(log_path).unlink()


def test_log_multiple_entries():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        log_path = f.name

    logger = AgentLogger(log_path)
    logger.log(trigger="speech", input_text="hello", tool_calls=[], response="hi")
    logger.log(trigger="proactive", input_text="fall detected", tool_calls=[], response="calling emergency")

    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 2

    Path(log_path).unlink()
