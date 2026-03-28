"""
Weather tool — fetch current weather conditions.

Used proactively when the user is about to go outside, or reactively
when they ask about the weather. Helps with practical reminders like
"bring an umbrella" or "it's cold, grab a jacket."
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from langchain_core.tools import tool

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")  # OpenWeatherMap API key
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "New York,US")


@tool
def weather_check(location: Optional[str] = None) -> dict:
    """Get current weather conditions and practical advice.

    Args:
        location: City name (e.g., "San Francisco,US"). Defaults to configured home location.

    Returns:
        Current conditions, temperature, and practical suggestions.
    """
    loc = location or DEFAULT_LOCATION

    if not WEATHER_API_KEY:
        return _fallback_response(loc)

    try:
        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": loc, "appid": WEATHER_API_KEY, "units": "imperial"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        description = data["weather"][0]["description"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]
        weather_main = data["weather"][0]["main"].lower()

        suggestions = _build_suggestions(temp, weather_main, wind_speed)

        return {
            "location": loc,
            "temperature_f": round(temp),
            "feels_like_f": round(feels_like),
            "conditions": description,
            "humidity_pct": humidity,
            "wind_mph": round(wind_speed),
            "suggestions": suggestions,
        }
    except Exception:
        return _fallback_response(loc)


def _build_suggestions(temp_f: float, weather_main: str, wind_mph: float) -> list[str]:
    suggestions = []

    if "rain" in weather_main or "drizzle" in weather_main:
        suggestions.append("Bring an umbrella — it's rainy outside.")
    if "snow" in weather_main:
        suggestions.append("It's snowing. Wear warm boots and be careful on slippery surfaces.")
    if temp_f < 45:
        suggestions.append("It's cold out. Make sure to grab a warm jacket.")
    elif temp_f < 60:
        suggestions.append("It's a bit chilly. A light jacket would be good.")
    elif temp_f > 90:
        suggestions.append("It's very hot. Stay hydrated and wear a hat if going outside.")
    if wind_mph > 20:
        suggestions.append("It's quite windy out there. Hold onto your hat!")

    if not suggestions:
        suggestions.append("Nice weather today. Enjoy your time outside!")

    return suggestions


def _fallback_response(location: str) -> dict:
    return {
        "location": location,
        "error": "Weather data unavailable",
        "suggestions": ["Unable to check weather right now. Dress in layers to be safe."],
    }
