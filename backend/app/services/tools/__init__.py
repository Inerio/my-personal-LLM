"""
Outils disponibles pour l'agent LangChain.
"""

from app.services.tools.web_search import web_search_tool
from app.services.tools.weather import weather_tool
from app.services.tools.wikipedia_tool import wikipedia_search_tool
from app.services.tools.calculator import calculator_tool
from app.services.tools.datetime_tool import datetime_tool

from app.config import settings


def get_available_tools() -> list:
    """
    Retourne la liste des outils disponibles selon la configuration.
    Les outils nécessitant une clé API sont exclus si la clé n'est pas configurée.
    """
    tools = []

    # Toujours disponibles
    tools.append(calculator_tool)
    tools.append(datetime_tool)
    tools.append(wikipedia_search_tool)

    # Web search : Tavily si clé dispo, sinon DuckDuckGo (toujours actif)
    tools.append(web_search_tool)

    if settings.openweathermap_api_key:
        tools.append(weather_tool)

    return tools
