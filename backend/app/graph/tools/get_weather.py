import requests
from langchain_core.tools import tool


@tool
def get_weather(latitude: float, longitude: float) -> dict:
    """
    Get the current weather for a given latitude and longitude.
    If you only have a city or location name, use get_lat_long first.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "current" in data:
            current = data["current"]
            return {
                "temperature_celsius": current.get("temperature_2m"),
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "time": current.get("time"),
            }

        return {"error": "Failed to fetch weather data."}

    except requests.RequestException as e:
        return {"error": f"Failed to fetch weather data: {str(e)}"}
