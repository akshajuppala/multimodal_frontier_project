import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI

from skills.twilio_call_skill import TOOL_SPEC, run_make_phone_call


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _extract_function_call(response: Any) -> Optional[Any]:
    for item in response.output:
        if item.type == "function_call" and item.name == "make_phone_call":
            return item
    return None


def _execute_skill(arguments_json: str) -> Dict[str, str]:
    arguments = json.loads(arguments_json)
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"
    if dry_run:
        return {"status": "ok", "call_sid": "DRY_RUN_CALL_SID"}
    return run_make_phone_call(
        to_number=arguments["to_number"],
        from_number=arguments["from_number"],
        message=arguments["message"],
    )


def run_llm_call_test() -> str:
    _load_dotenv()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    to_number = os.getenv("TWILIO_TO_NUMBER", "+13467636380")
    from_number = os.getenv("TWILIO_FROM_NUMBER", "+12603466955")
    message = os.getenv(
        "TWILIO_TEST_MESSAGE",
        "Please Help. There's a person named David in the need of medical assistance at 660 Market Street",
    )

    prompt = (
        "You can use the make_phone_call tool. "
        "Call this exact destination with this exact sender and message. "
        f"to_number={to_number}, from_number={from_number}, message={message}"
    )

    first_response = client.responses.create(
        model=model,
        input=prompt,
        tools=[TOOL_SPEC],
    )

    function_call = _extract_function_call(first_response)
    if not function_call:
        raise RuntimeError("Model did not call make_phone_call.")

    tool_result = _execute_skill(function_call.arguments)
    second_response = client.responses.create(
        model=model,
        previous_response_id=first_response.id,
        input=[
            {
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(tool_result),
            }
        ],
    )
    return second_response.output_text


if __name__ == "__main__":
    print(run_llm_call_test())
