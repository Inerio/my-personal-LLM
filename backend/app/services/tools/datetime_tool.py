"""
Outil Date/Heure — Informations temporelles
Permet à l'agent de connaître la date et l'heure actuelles.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from langchain_core.tools import tool


@tool
def datetime_tool(timezone_name: str = "Europe/Paris") -> str:
    """
    Retourne la date et l'heure actuelles.
    Utilise cet outil quand l'utilisateur demande la date, l'heure,
    ou le jour de la semaine.

    Args:
        timezone_name: Nom du fuseau horaire IANA (ex: "Europe/Paris", "America/New_York").
                       Par défaut: Europe/Paris (gère automatiquement CET/CEST).

    Returns:
        Date et heure actuelles formatées
    """
    # Heure UTC
    utc_now = datetime.now(timezone.utc)

    # Heure locale avec fuseau horaire complet (gère DST automatiquement)
    try:
        tz = ZoneInfo(timezone_name)
    except (KeyError, Exception):
        tz = ZoneInfo("Europe/Paris")
    local_now = utc_now.astimezone(tz)
    timezone_offset = local_now.utcoffset().total_seconds() / 3600

    # Jours de la semaine en français
    jours_fr = [
        "Lundi", "Mardi", "Mercredi", "Jeudi",
        "Vendredi", "Samedi", "Dimanche"
    ]
    # Mois en français
    mois_fr = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]

    jour_semaine = jours_fr[local_now.weekday()]
    jour = local_now.day
    mois = mois_fr[local_now.month]
    annee = local_now.year
    heure = local_now.strftime("%H:%M:%S")

    offset_int = int(timezone_offset)
    tz_name = f"UTC{'+' if offset_int >= 0 else ''}{offset_int}"

    return (
        f"**{jour_semaine} {jour} {mois} {annee}**\n"
        f"**{heure}** ({tz_name})\n"
        f"Timestamp UNIX: {int(utc_now.timestamp())}"
    )
