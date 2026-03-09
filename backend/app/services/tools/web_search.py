"""
Outil de recherche web — Gustave Code

Ordre de priorité :
1. Tavily    (premium, si clé API configurée)
2. duckduckgo-search  (librairie, si installée)
3. DuckDuckGo HTML    (httpx direct, toujours dispo — zéro dépendance)

Fallback automatique Tavily → DuckDuckGo en cas de quota épuisé.
"""

import logging
import re
from urllib.parse import unquote

from langchain_core.tools import tool
from app.config import settings

logger = logging.getLogger(__name__)

# Flag session : True dès que Tavily refuse pour quota/rate-limit
_tavily_exhausted = False

# Détection de duckduckgo-search au chargement du module
_HAS_DDGS = False
try:
    from duckduckgo_search import DDGS
    _HAS_DDGS = True
    logger.info("duckduckgo-search disponible")
except ImportError:
    logger.info("duckduckgo-search non installé — fallback httpx")


def _is_quota_error(exc: Exception) -> bool:
    """Détecte si l'erreur Tavily est liée au quota / rate-limit."""
    msg = str(exc).lower()
    return any(k in msg for k in (
        "rate limit", "rate_limit", "ratelimit",
        "quota", "insufficient", "credit",
        "429", "402", "limit exceeded", "usage limit",
    ))


# ================================================================
# Backend 1 : Tavily (premium)
# ================================================================

def _search_tavily(query: str, max_results: int = 5) -> str:
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key, timeout=15)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_answer=True,
        include_raw_content=False,
    )

    results = []
    if response.get("answer"):
        results.append(f"**Résumé:** {response['answer']}\n")

    for i, r in enumerate(response.get("results", []), 1):
        title = r.get("title", "Sans titre")
        url = r.get("url", "")
        content = r.get("content", "")
        results.append(f"**{i}. {title}**\n{content}\nSource: {url}\n")

    return "\n".join(results) if results else "Aucun résultat trouvé."


# ================================================================
# Backend 2 : duckduckgo-search (librairie)
# ================================================================

def _search_ddgs_lib(query: str, max_results: int = 5) -> str:
    with DDGS() as ddgs:
        raw_results = list(ddgs.text(query, max_results=max_results))

    if not raw_results:
        return "Aucun résultat trouvé."

    results = []
    for i, r in enumerate(raw_results, 1):
        title = r.get("title", "Sans titre")
        url = r.get("href", "")
        body = r.get("body", "")
        results.append(f"**{i}. {title}**\n{body}\nSource: {url}\n")

    return "\n".join(results)


# ================================================================
# Backend 3 : DuckDuckGo HTML via httpx (toujours disponible)
# ================================================================

_DDG_HTML_URL = "https://html.duckduckgo.com/html/"
_DDG_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Patterns pour parser les résultats DuckDuckGo HTML
_RE_RESULT = re.compile(
    r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_RE_SNIPPET = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
    re.DOTALL,
)
_RE_TAGS = re.compile(r'<[^>]+>')


def _search_ddg_httpx(query: str, max_results: int = 5) -> str:
    """Recherche DuckDuckGo via HTTP direct (zéro dépendance externe)."""
    import httpx

    resp = httpx.post(
        _DDG_HTML_URL,
        data={"q": query, "b": ""},
        headers={"User-Agent": _DDG_UA},
        timeout=15,
        follow_redirects=True,
    )
    resp.raise_for_status()
    html = resp.text

    links = _RE_RESULT.findall(html)[:max_results]
    snippets = _RE_SNIPPET.findall(html)

    if not links:
        return "Aucun résultat trouvé."

    results = []
    for i, (raw_url, raw_title) in enumerate(links):
        title = _RE_TAGS.sub('', raw_title).strip()
        snippet = _RE_TAGS.sub('', snippets[i]).strip() if i < len(snippets) else ""

        # DuckDuckGo redirige via un proxy — extraire l'URL réelle
        url = raw_url
        uddg = re.search(r'uddg=([^&]+)', raw_url)
        if uddg:
            url = unquote(uddg.group(1))

        results.append(f"**{i + 1}. {title}**\n{snippet}\nSource: {url}\n")

    return "\n".join(results)


# ================================================================
# Fonction DuckDuckGo unifiée (lib → httpx fallback)
# ================================================================

def _search_duckduckgo(query: str, max_results: int = 5) -> str:
    """DuckDuckGo : utilise la lib si dispo, sinon httpx direct."""
    if _HAS_DDGS:
        try:
            return _search_ddgs_lib(query, max_results)
        except Exception as e:
            logger.warning(f"duckduckgo-search échoué: {e} — fallback httpx")

    return _search_ddg_httpx(query, max_results)


# ================================================================
# Outil LangChain
# ================================================================

@tool
def web_search_tool(query: str) -> str:
    """
    Recherche des informations sur internet en temps réel.
    Utilise cet outil quand l'utilisateur pose une question sur l'actualité,
    des faits récents, ou quand tu as besoin de vérifier une information.

    Args:
        query: La requête de recherche (en français ou anglais)

    Returns:
        Résultats de recherche formatés avec sources
    """
    global _tavily_exhausted

    use_tavily = settings.tavily_api_key and not _tavily_exhausted

    # --- Tentative Tavily (premium) ---
    if use_tavily:
        try:
            logger.info(f"Recherche Tavily: {query}")
            return _search_tavily(query)
        except Exception as e:
            logger.error(f"Erreur Tavily: {e}")
            if _is_quota_error(e):
                _tavily_exhausted = True
                logger.warning(
                    "Quota Tavily épuisé — bascule vers DuckDuckGo "
                    "pour le reste de la session"
                )
            else:
                logger.info("Fallback vers DuckDuckGo...")

    # --- DuckDuckGo (gratuit, toujours disponible) ---
    try:
        logger.info(f"Recherche DuckDuckGo: {query}")
        return _search_duckduckgo(query)
    except Exception as e2:
        logger.error(f"Erreur DuckDuckGo: {e2}")
        return f"Erreur lors de la recherche: {str(e2)}"
