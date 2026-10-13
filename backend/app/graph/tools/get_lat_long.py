import requests
from langchain_core.tools import tool


@tool
def get_lat_long(city_name: str) -> dict:
    """Get the latitude and longitude for a given city or location name."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "results" in data and len(data["results"]) > 0:
            loc = data["results"][0]
            return {
                "name": loc.get("name"),
                "country": loc.get("country"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
            }

        return {"error": f"Location '{city_name}' not found."}

    except requests.RequestException as e:
        return {"error": f"Failed to fetch location data: {str(e)}"}
