import json
from crewai import Agent, LLM
from crewai.tools import tool
import os

SEUIL_ECART_METHODES  = 0.30   # 30% d'écart max entre DCF et Multiples
SEUIL_VALEUR_TERMINALE = 0.85  # 85% max de la VE en valeur terminale
MAX_ITERATIONS         = 3


@tool("Auditer les résultats DCF et Comparables")
def auditer_resultats(
    resultat_dcf: str,
    resultat_multiples: str,
    iteration: int = 1
) -> str:
    """
    Audite les résultats des deux agents analystes.
    Bloque si :
      - Écart entre DCF et Multiples > 30%
      - Valeur Terminale > 85% de la VE DCF
    Retourne instructions de correction chiffrées ou validation.
    """
    try:
        dcf  = json.loads(resultat_dcf)
        mult = json.loads(resultat_multiples)
    except Exception as e:
        return json.dumps({"statut": "ERREUR", "message": f"JSON invalide : {e}"})

    if iteration > MAX_ITERATIONS:
        return json.dumps({
            "statut": "FORCE_VALIDATION",
            "message": (
                f"Limite de {MAX_ITERATIONS} itérations atteinte. "
                "Les résultats sont acceptés avec réserves — "
                "l'agent synthèse doit mentionner les divergences."
            )
        })

    problemes   = []
    corrections = []

    ve_dcf  = dcf.get("enterprise_value", 0)
    ve_mult = mult.get("valeur_multiples", 0)
    pct_terminal = dcf.get("pct_terminal", 0)

    # ── Vérification 1 : écart entre méthodes ────────────────────────────
    if ve_dcf > 0 and ve_mult > 0:
        ecart = abs(ve_dcf - ve_mult) / max(ve_dcf, ve_mult)
        if ecart > SEUIL_ECART_METHODES:
            problemes.append(
                f"Écart entre DCF ({ve_dcf:,.0f}) et Multiples ({ve_mult:,.0f}) "
                f"= {ecart:.1%} > seuil {SEUIL_ECART_METHODES:.0%}"
            )
            # Correction chiffrée : ajustement WACC suggéré
            wacc_actuel = dcf.get("wacc", 0)
            if ve_dcf > ve_mult:
                wacc_suggere = wacc_actuel + 0.01
                corrections.append(
                    f"DCF surestime : augmenter le WACC de {wacc_actuel:.2%} "
                    f"→ {wacc_suggere:.2%} (+100 bps) OU vérifier les multiples comparables "
                    f"(EV/EBITDA médian retenu : {mult.get('multiples_utilises', {}).get('EV/EBITDA', 'N/A')}x)."
                )
            else:
                wacc_suggere = wacc_actuel - 0.005
                corrections.append(
                    f"DCF sous-estime : réduire le WACC de {wacc_actuel:.2%} "
                    f"→ {wacc_suggere:.2%} (-50 bps) OU exclure les multiples "
                    "comparables les plus élevés."
                )

    # ── Vérification 2 : poids valeur terminale ───────────────────────────
    if pct_terminal > SEUIL_VALEUR_TERMINALE:
        problemes.append(
            f"Valeur Terminale représente {pct_terminal:.1%} du DCF "
            f"> seuil {SEUIL_VALEUR_TERMINALE:.0%} — modèle trop dépendant "
            "de la valeur terminale."
        )
        tg_actuel = dcf.get("terminal_growth", 0)
        wacc_actuel = dcf.get("wacc", 0)
        corrections.append(
            f"Réduire le taux de croissance terminal de {tg_actuel:.2%} "
            f"→ {max(tg_actuel - 0.005, 0):.2%} (-50 bps) "
            f"OU augmenter le WACC de {wacc_actuel:.2%} "
            f"→ {wacc_actuel + 0.01:.2%} (+100 bps) "
            "pour rééquilibrer la décomposition de valeur."
        )

    # ── Résultat de l'audit ───────────────────────────────────────────────
    if problemes:
        return json.dumps({
            "statut":      "BLOQUE",
            "iteration":   iteration,
            "problemes":   problemes,
            "corrections": corrections,
            "instruction": (
                f"Itération {iteration}/{MAX_ITERATIONS} — "
                "Appliquer les corrections ci-dessus et relancer les calculs."
            )
        })

    return json.dumps({
        "statut":    "VALIDE",
        "iteration": iteration,
        "message":   "Résultats conformes aux seuils de qualité.",
        "resume": {
            "ve_dcf":        ve_dcf,
            "ve_multiples":  ve_mult,
            "ecart":         round(abs(ve_dcf - ve_mult) / max(ve_dcf, ve_mult, 1), 4),
            "pct_terminal":  pct_terminal,
        }
    })


def creer_agent_critique():
    return Agent(
        role="Auditeur financier senior",
        goal=(
            "Auditer les résultats du DCF et des Multiples avant agrégation. "
            "Bloquer le processus si l'écart dépasse 30% ou si la valeur terminale "
            "dépasse 85% du DCF. "
            "Fournir des instructions de correction chiffrées et précises. "
            "Valider après correction ou forcer la validation après 3 itérations."
        ),
        backstory=(
            "Tu es auditeur financier senior avec 20 ans d'expérience sur les marchés "
            "émergents et marocain. Tu es méticuleux, rigoureux et impartial. "
            "Tu ne valides JAMAIS un modèle sans vérifier : "
            "1) la cohérence entre DCF et Multiples (écart max 30%), "
            "2) le poids de la valeur terminale (max 85% du DCF). "
            "Tes corrections sont toujours chiffrées, précises et actionnables. "
            "Tu n'es pas influençable par les agents analystes."
        ),
        tools=[auditer_resultats],
        llm="azure/gpt-4.1-nano",  # même Azure que les autres
        verbose=True,
        max_iter=5,          # plus d'itérations pour être plus rigoureux
        max_retry_limit=2,
    )