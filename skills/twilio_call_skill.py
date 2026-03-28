from typing import Any, Dict

from skills.call import make_call


TOOL_SPEC: Dict[str, Any] = {
    "type": "function",
    "name": "make_phone_call",
    "description": "Place an outbound phone call with a spoken text-to-speech message.",
    "parameters": {
        "type": "object",
        "properties": {
            "to_number": {
                "type": "string",
                "description": "E.164 destination number, for example +13467636380",
            },
            "from_number": {
                "type": "string",
                "description": "E.164 Twilio number that will place the call.",
            },
            "message": {
                "type": "string",
                "description": "Text that Twilio will speak during the call.",
            },
        },
        "required": ["to_number", "from_number", "message"],
        "additionalProperties": False,
    },
}


def run_make_phone_call(to_number: str, from_number: str, message: str) -> Dict[str, str]:
    """Wrapper used by LLM tool-calling loops."""
    call_sid = make_call(to_number=to_number, from_number=from_number, message=message)
    return {"status": "ok", "call_sid": call_sid}
