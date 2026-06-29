import json
from crewai import Agent
from crewai.tools import tool
from crewai_tools import SerperDevTool


@tool("Calculer la valeur par multiples")
def calculer_multiples(
    ebitda: float,
    resultat_net: float,
    ev_ebitda: float,
    pe: float,
    poids_ev_ebitda: float = 0.60,
    poids_pe: float        = 0.40,
) -> str:
    """
    Valorise l'entreprise par 2 multiples :
    - EV/EBITDA (60%)
    - P/E       (40%)
    """
    try:
        val_ev_ebitda = ebitda       * ev_ebitda
        val_pe        = resultat_net * pe

        valeur_agregee = (
            val_ev_ebitda * poids_ev_ebitda +
            val_pe        * poids_pe
        )

        return json.dumps({
            "valeur_ev_ebitda": round(val_ev_ebitda, 2),
            "valeur_pe":        round(val_pe,        2),
            "valeur_multiples": round(valeur_agregee, 2),
            "multiples_utilises": {
                "EV/EBITDA": ev_ebitda,
                "P/E":       pe,
            },
            "ponderation": {
                "EV/EBITDA": poids_ev_ebitda,
                "P/E":       poids_pe,
            }
        })
    except Exception as e:
        return json.dumps({"erreur": str(e)})


def creer_agent_comparables():
    return Agent(
        role="Analyste Comparables boursiers",
        goal=(
            "1) Rechercher via web 1 à 3 entreprises comparables RÉELLES et cotées "
            "dans le même secteur (priorité : bourse locale → MENA → Europe → US). "
            "2) Extraire leurs multiples EV/EBITDA et P/E uniquement. "
            "3) Ne JAMAIS inventer de comparables — si aucun trouvé, retourner "
            "comparables_proposes vide. "
            "4) Appeler calculer_multiples() avec les multiples médians retenus."
        ),
        backstory=(
            "Tu es expert en analyse boursière comparative. "
            "Tu travailles uniquement avec des données réelles et vérifiables. "
            "Tu signales tout multiple aberrant (EV/EBITDA > 20x ou négatif, P/E > 50x). "
            "Tu précises toujours la source et la date des multiples trouvés."
        ),
        tools=[SerperDevTool(), calculer_multiples],
        llm="azure/gpt-4.1-nano",
        verbose=True
    )