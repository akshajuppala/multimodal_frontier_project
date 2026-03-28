"""Weather skill — current conditions and practical advice for going outside."""
from __future__ import annotations

import logging
import os

import httpx
import railtracks as rt

logger = logging.getLogger(__name__)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "New York,US")


@rt.function_node
def weather_check(location: str = "") -> str:
    """Get current weather conditions and practical suggestions for going outside.

    Args:
        location (str): City name (e.g. "San Francisco,US"). Defaults to configured home location.
    """
    loc = location or DEFAULT_LOCATION

    if not WEATHER_API_KEY:
        return f"Weather data unavailable (no API key). Location: {loc}. Dress in layers to be safe."

    try:
        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": loc, "appid": WEATHER_API_KEY, "units": "imperial"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        temp = round(data["main"]["temp"])
        feels = round(data["main"]["feels_like"])
        desc = data["weather"][0]["description"]
        wind = round(data["wind"]["speed"])
        main = data["weather"][0]["main"].lower()

        lines = [f"Weather in {loc}: {desc}, {temp}°F (feels like {feels}°F), wind {wind} mph."]
        lines.append("")

        if "rain" in main or "drizzle" in main:
            lines.append("Bring an umbrella — it's rainy outside.")
        if "snow" in main:
            lines.append("It's snowing. Wear warm boots and be careful on slippery surfaces.")
        if temp < 45:
            lines.append("It's cold out. Make sure to grab a warm jacket.")
        elif temp < 60:
            lines.append("It's a bit chilly. A light jacket would be good.")
        elif temp > 90:
            lines.append("It's very hot. Stay hydrated and wear a hat.")
        if wind > 20:
            lines.append("It's quite windy out there.")

        if len(lines) == 2:
            lines.append("Nice weather today. Enjoy your time outside!")

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"Weather API error: {e}")
        return f"Couldn't check weather right now for {loc}. Dress in layers to be safe."
