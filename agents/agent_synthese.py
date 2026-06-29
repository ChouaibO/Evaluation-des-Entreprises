import os
from crewai import Agent
from crewai.tools import tool
from datetime import datetime


@tool("Sauvegarder le rapport")
def sauvegarder_rapport(contenu: str) -> str:
    """
    Sauvegarde le rapport final dans outputs/.
    Crée deux fichiers :
      - rapport_valorisation.txt      (nom fixe pour l'UI)
      - rapport_valorisation_TIMESTAMP.txt  (archive horodatée)
    """
    os.makedirs("outputs", exist_ok=True)

    # Fichier fixe lu par l'UI
    chemin_fixe = "outputs/rapport_valorisation.txt"
    with open(chemin_fixe, "w", encoding="utf-8") as f:
        f.write(contenu)

    # Archive horodatée
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin_archive = f"outputs/rapport_valorisation_{timestamp}.txt"
    with open(chemin_archive, "w", encoding="utf-8") as f:
        f.write(contenu)

    return f"✅ Rapport sauvegardé : {chemin_fixe} (archive : {chemin_archive})"


def creer_agent_synthese():
    return Agent(
        role="Rédacteur du rapport final",
        goal=(
            "Produire un rapport de valorisation complet, clair et structuré, "
            "puis le sauvegarder via sauvegarder_rapport(). "
            "Le rapport doit couvrir : valeur DCF, valeur par multiples, "
            "fourchette pessimiste/centrale/optimiste, valeur par action, "
            "paramètres clés, comparables retenus, statut audit qualité, "
            "risques et recommandation finale."
        ),
        backstory=(
            "Tu es expert en communication financière pour le marché marocain. "
            "Tu synthétises des analyses complexes en conclusions claires et actionnables. "
            "Tu ne sautes jamais l'appel à sauvegarder_rapport()."
        ),
        tools=[sauvegarder_rapport],
        llm="azure/gpt-4.1-nano",
        verbose=True
    )