"""
Outil Calculatrice — Évaluation d'expressions mathématiques
Permet à l'agent d'effectuer des calculs précis.
"""

import logging
import math
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Fonctions mathématiques sûres accessibles dans les expressions
SAFE_MATH_GLOBALS = {
    "__builtins__": {},
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    "int": int,
    "float": float,
    # Module math
    "pi": math.pi,
    "e": math.e,
    "sqrt": math.sqrt,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
    "gcd": math.gcd,
    "degrees": math.degrees,
    "radians": math.radians,
    "exp": math.exp,
    "inf": math.inf,
}


@tool
def calculator_tool(expression: str) -> str:
    """
    Évalue une expression mathématique et retourne le résultat.
    Utilise cet outil pour tout calcul numérique.
    Supporte: +, -, *, /, **, %, sqrt(), log(), sin(), cos(), pi, etc.

    Args:
        expression: Expression mathématique à évaluer
                    Exemples: "2 + 2", "sqrt(144)", "sin(pi/4)", "15% de 200"

    Returns:
        Le résultat du calcul
    """
    try:
        # Nettoyage de l'expression
        expr = expression.strip()

        # Limite de longueur pour éviter les abus
        if len(expr) > 500:
            return "Expression trop longue (max 500 caracteres)"

        # Gestion des pourcentages courants
        expr = expr.replace("% de ", "/100 * ")
        expr = expr.replace("% of ", "/100 * ")

        # Remplacer les notations françaises
        expr = expr.replace(",", ".")
        expr = expr.replace("×", "*")
        expr = expr.replace("÷", "/")
        expr = expr.replace("^", "**")

        # Évaluation sécurisée
        result = eval(expr, SAFE_MATH_GLOBALS, {})

        # Formater le résultat
        if isinstance(result, float):
            # Éviter les résultats du type 2.0000000000001
            if result == int(result) and not math.isinf(result):
                result = int(result)
            else:
                result = round(result, 10)

        return f"{expression} = **{result}**"

    except ZeroDivisionError:
        return "Erreur: Division par zero"
    except SyntaxError:
        return f"Expression invalide: '{expression}'. Verifie la syntaxe."
    except Exception as e:
        logger.error(f"Erreur calcul: {e}")
        return f"Erreur de calcul: {str(e)}"
