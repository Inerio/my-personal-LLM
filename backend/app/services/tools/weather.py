"""
Outil météo — OpenWeatherMap API
Permet à l'agent d'obtenir la météo actuelle d'une ville.
"""

import logging
import httpx
from langchain_core.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)


@tool
def weather_tool(city: str) -> str:
    """
    Obtient la météo actuelle pour une ville donnée.
    Utilise cet outil quand l'utilisateur demande la météo ou les conditions climatiques.

    Args:
        city: Nom de la ville (ex: "Paris", "Lyon", "New York")

    Returns:
        Informations météo formatées
    """
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": settings.openweathermap_api_key,
            "units": "metric",
            "lang": "fr",
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Extraire les données
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"]
        wind_speed = data["wind"]["speed"]
        city_name = data["name"]
        country = data["sys"]["country"]

        # Pression et visibilité
        pressure = data["main"]["pressure"]
        visibility = data.get("visibility", "N/A")
        if isinstance(visibility, (int, float)):
            visibility = f"{visibility / 1000:.1f} km"

        return (
            f"Meteo a {city_name}, {country}:\n"
            f"- Conditions: {description.capitalize()}\n"
            f"- Température: {temp:.1f}°C (ressenti: {feels_like:.1f}°C)\n"
            f"- Humidité: {humidity}%\n"
            f"- Vent: {wind_speed * 3.6:.1f} km/h\n"
            f"- Pression: {pressure} hPa\n"
            f"- Visibilité: {visibility}"
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Ville '{city}' non trouvée. Vérifie l'orthographe."
        logger.error(f"Erreur API météo: {e}")
        return f"Erreur API météo: {str(e)}"
    except Exception as e:
        logger.error(f"Erreur météo: {e}")
        return f"Erreur lors de la récupération météo: {str(e)}"
