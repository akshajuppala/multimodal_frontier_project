import os
from pathlib import Path
from twilio.rest import Client


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def make_call(
    to_number: str,
    from_number: str,
    message: str = "Please Help. There's a person named David in the need of medical assistance at 660 Market Street",
) -> str:
    """Place a Twilio call and return the new call SID."""
    _load_dotenv()
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        raise ValueError(
            "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )

    client = Client(account_sid, auth_token)
    call = client.calls.create(
        twiml=f"<Response><Say>{message}</Say></Response>",
        to=to_number,
        from_=from_number,
    )
    return call.sid


if __name__ == "__main__":
    _load_dotenv()
    to_number = os.getenv("TWILIO_TO_NUMBER")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not to_number or not from_number:
        raise ValueError(
            "Missing phone numbers. Set TWILIO_TO_NUMBER and TWILIO_FROM_NUMBER."
        )
    print(make_call(to_number=to_number, from_number=from_number))