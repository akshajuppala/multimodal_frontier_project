import logging

from railtracks import function_node
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from src.config import settings

logger = logging.getLogger(__name__)


def make_emergency_call(reason: str) -> str:
    """Place an emergency call via Twilio."""
    if not settings.twilio_account_sid or not settings.emergency_contact_number:
        logger.warning("Twilio not configured — skipping emergency call")
        return "Emergency call skipped: Twilio not configured."

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    twiml = VoiceResponse()
    twiml.say(
        f"This is an automated alert from the caregiver assistant. {reason}. "
        "Please check on the patient immediately.",
        voice="alice",
    )

    call = client.calls.create(
        twiml=str(twiml),
        to=settings.emergency_contact_number,
        from_=settings.twilio_from_number,
    )

    logger.info(f"Emergency call initiated: SID={call.sid}, reason={reason}")
    return f"Emergency call placed (SID: {call.sid}). Reason: {reason}"


@function_node
def call_emergency(reason: str) -> str:
    """Call the emergency contact via phone. Only use this for genuine emergencies such as falls, fires, or medical distress. Provide a clear reason for the call."""
    return make_emergency_call(reason)
