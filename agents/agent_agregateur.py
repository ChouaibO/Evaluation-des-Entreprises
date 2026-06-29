import json
from crewai import Agent
from crewai.tools import tool
import os

POIDS_DCF_DEFAUT       = 0.60
POIDS_MULTIPLES_DEFAUT = 0.40

@tool("Agréger DCF et Multiples en valeur finale")
def agreger_valorisation(
    resultat_dcf: str,
    resultat_multiples: str,
    dette_nette: float,
    nombre_actions: float,
    poids_dcf: float       = 0.60,
    poids_multiples: float = 0.40,
) -> str:
    """Agrège DCF et Multiples en valeur finale avec fourchette pessimiste/centrale/optimiste."""
    try:
        dcf  = json.loads(resultat_dcf)
        mult = json.loads(resultat_multiples)
    except Exception as e:
        return json.dumps({"erreur": f"JSON invalide : {e}"})

    ve_dcf  = dcf.get("enterprise_value", 0)
    ve_mult = mult.get("valeur_multiples", 0)

    # ── Détection mode DCF pur ────────────────────────────────────────────
    pas_de_multiples = (
        ve_mult == 0
        or not mult.get("comparables_proposes")
        or mult.get("note", "").startswith("Aucun comparable")
    )

    if pas_de_multiples:
        # DCF pur : 100% pondération sur le DCF
        ve_centrale   = ve_dcf
        poids_dcf_reel     = 1.0
        poids_mult_reel    = 0.0
        methode_utilisee   = "DCF uniquement (aucun comparable retenu)"
    else:
        ve_centrale        = ve_dcf * poids_dcf + ve_mult * poids_multiples
        poids_dcf_reel     = poids_dcf
        poids_mult_reel    = poids_multiples
        methode_utilisee   = f"DCF ({poids_dcf:.0%}) + Multiples ({poids_multiples:.0%})"

    ve_pessimiste = ve_centrale * 0.85
    ve_optimiste  = ve_centrale * 1.15

    eq_centrale   = max(ve_centrale   - dette_nette, 0)
    eq_pessimiste = max(ve_pessimiste - dette_nette, 0)
    eq_optimiste  = max(ve_optimiste  - dette_nette, 0)

    if nombre_actions and nombre_actions > 0:
        vpa_centrale = eq_centrale / nombre_actions
        vpa_pessimiste = eq_pessimiste / nombre_actions
        vpa_optimiste = eq_optimiste / nombre_actions
    else:
        vpa_centrale = None
        vpa_pessimiste = None
        vpa_optimiste = None

    resultat = {
        "valeur_entreprise": {
            "centrale":   round(ve_centrale,   2),
            "pessimiste": round(ve_pessimiste, 2),
            "optimiste":  round(ve_optimiste,  2),
        },
        "valeur_capitaux_propres": {
            "centrale":   round(eq_centrale,   2),
            "pessimiste": round(eq_pessimiste, 2),
            "optimiste":  round(eq_optimiste,  2),
        },
        "valeur_par_action": {
            "centrale":   round(vpa_centrale,   2) if vpa_centrale   else None,
            "pessimiste": round(vpa_pessimiste, 2) if vpa_pessimiste else None,
            "optimiste":  round(vpa_optimiste,  2) if vpa_optimiste  else None,
        },
        "composition": {
            "ve_dcf":          round(ve_dcf,  2),
            "ve_multiples":    round(ve_mult, 2),
            "poids_dcf":       poids_dcf_reel,
            "poids_multiples": poids_mult_reel,
            "methode":         methode_utilisee,   # ✅ tracé pour le rapport
            "dette_nette":     dette_nette,
        },
        "wacc":            dcf.get("wacc"),
        "terminal_growth": dcf.get("terminal_growth"),
        "pct_terminal":    dcf.get("pct_terminal"),
        "fcf_forecast":    dcf.get("fcf_forecast"),
    }

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/resultats_agregation.json", "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=2)

    return json.dumps(resultat)
def creer_agent_agregateur():
    return Agent(
        role="Agrégateur de valorisation",
        goal=(
            "Combiner les résultats du DCF et des Multiples en une valeur finale "
            "avec fourchette pessimiste / centrale / optimiste et valeur par action. "
            "Appliquer la pondération 60% DCF / 40% Multiples par défaut, "
            "ou celle définie par l'utilisateur."
        ),
        backstory=(
            "Tu es directeur de valorisation. Tu produis une synthèse claire "
            "et structurée combinant les deux méthodes. "
            "Tu expliques toujours la pondération retenue et les limites du modèle."
        ),
        tools=[agreger_valorisation],
        llm="azure/gpt-4.1-nano",
        verbose=True
    )