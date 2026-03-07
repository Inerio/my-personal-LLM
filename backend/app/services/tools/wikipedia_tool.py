"""
Outil Wikipedia — Recherche encyclopédique
Permet à l'agent de chercher des informations factuelles sur Wikipedia.
"""

import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def wikipedia_search_tool(query: str) -> str:
    """
    Recherche des informations sur Wikipedia.
    Utilise cet outil pour des questions factuelles, historiques,
    scientifiques ou encyclopédiques.

    Args:
        query: Le sujet à rechercher sur Wikipedia

    Returns:
        Résumé de l'article Wikipedia trouvé
    """
    try:
        import wikipedia

        # Chercher en français d'abord
        wikipedia.set_lang("fr")

        try:
            # Recherche directe
            page = wikipedia.page(query, auto_suggest=True)
            summary = wikipedia.summary(query, sentences=8)

            return (
                f"**{page.title}** (Wikipedia FR)\n\n"
                f"{summary}\n\n"
                f"Source: {page.url}"
            )
        except wikipedia.exceptions.DisambiguationError as e:
            # Page de désambiguïsation — prendre le premier résultat
            if e.options:
                first_option = e.options[0]
                summary = wikipedia.summary(first_option, sentences=6)
                return (
                    f"**{first_option}** (Wikipedia FR)\n\n"
                    f"{summary}\n\n"
                    f"Autres suggestions: {', '.join(e.options[:5])}"
                )
            return f"Plusieurs résultats trouvés: {', '.join(e.options[:10])}"

        except wikipedia.exceptions.PageError:
            # Pas trouvé en FR, essayer en EN
            wikipedia.set_lang("en")
            try:
                page = wikipedia.page(query, auto_suggest=True)
                summary = wikipedia.summary(query, sentences=8)
                return (
                    f"**{page.title}** (Wikipedia EN)\n\n"
                    f"{summary}\n\n"
                    f"Source: {page.url}"
                )
            except Exception:
                return f"Aucun article Wikipedia trouvé pour '{query}'."

    except Exception as e:
        logger.error(f"Erreur Wikipedia: {e}")
        return f"Erreur lors de la recherche Wikipedia: {str(e)}"
