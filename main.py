import sys
from crewai import Task, Crew, Process
from dotenv import load_dotenv

from agents.agent_collecteur   import creer_agent_collecteur
from agents.agent_analyste     import creer_agent_analyste
from agents.agent_comparable  import creer_agent_comparables
from agents.agent_critique     import creer_agent_critique
from agents.agent_agregateur   import creer_agent_agregateur
from agents.agent_synthese     import creer_agent_synthese

import litellm
litellm.drop_params = True

load_dotenv()

MAX_ITERATIONS = 3


def lancer_phase1(file_path: str, mode: str = "libre"):
    """
    Phase 1 : Collecteur → DCF → Comparables
    S'arrête et attend la validation des comparables par l'utilisateur.
    """
    agent_collecteur  = creer_agent_collecteur()
    agent_analyste    = creer_agent_analyste()
    agent_comparables = creer_agent_comparables()

    tache_collecte = Task(
        description=f"""
        Lis le fichier : {file_path}
        Utilise l'outil '{"lire_template_excel" if mode == "template" else "lire_document_libre"}'.
        
        IMPORTANT — UNITÉS :
            Détecte l'unité utilisée dans le document (MAD, kMAD, MMAD, Milliards MAD).
            Convertis TOUTES les valeurs numériques en MAD avant de les retourner.
            Indique l'unité d'origine dans le JSON : "unite_origine": "kMAD"
            Exemple : si le document dit 850 000 kMAD → retourne 850 000 000 MAD

        Extrais et structure les données suivantes pour N-3, N-2, N-1 :
        - Informations générales : nom_entreprise, secteur, nombre_actions, prix_action
        - Compte de résultat : chiffre_affaires, ebit, ebitda, da, resultat_net, taux_is
        - Bilan : capitaux_propres, dette_nette
        - Flux : capex, variation_bfr
        - WACC (si fournis) : cout_dette, beta, taux_sans_risque, prime_risque_marche
        - Taux de croissance (si fourni) : taux_croissance_ct, taux_croissance_terminal

        Signale explicitement toute donnée manquante.
        Retourne un JSON structuré.
        """,
        expected_output="JSON structuré avec toutes les données financières extraites.",
        agent=agent_collecteur
    )

    tache_dcf = Task(
        description="""
        À partir des données collectées, construis le modèle DCF en 3 étapes :

        ÉTAPE 1 — WACC : appelle calculer_wacc().
        Si paramètres manquants, estime avec justification :
          - beta selon secteur (marché marocain)
          - taux_sans_risque : BDT 10 ans ≈ 3.8%
          - prime_risque_marche : Maroc ≈ 6.5%

        ÉTAPE 2 — FCF projetés : appelle projeter_fcf() avec listes [N-3, N-2, N-1].
        Si taux_croissance absent, estime depuis TCAM historique du CA.

        ÉTAPE 3 — Valeur DCF : appelle calculer_dcf().

        Retourne JSON complet avec enterprise_value, pv_fcf, pv_terminal,
        pct_terminal, wacc, terminal_growth, fcf_forecast.
        """,
        expected_output=(
            "JSON avec enterprise_value, pv_fcf, pv_terminal, pct_terminal, "
            "wacc, terminal_growth, fcf_forecast et justification des hypothèses."
        ),
        agent=agent_analyste,
        context=[tache_collecte]
    )

    tache_comparables = Task(
        description="""
        À partir du secteur et des données collectées :

        ÉTAPE 1 — Recherche comparables :
        Recherche 1 à 3 entreprises comparables cotées dans le même secteur
        (priorité : Bourse de Casablanca → MENA → Europe).
        Pour chaque comparable : nom, EV/EBITDA, P/E, EV/CA.
        Signale tout multiple aberrant (EV/EBITDA > 20x ou négatif).

        ÉTAPE 2 — Calcul par multiples :
        Appelle calculer_multiples() avec les multiples médians.

        Retourne un JSON avec :
        {
          "comparables_proposes": [
            {"nom": "...", "ev_ebitda": x, "pe": x, "ev_ca": x, "aberrant": false},
            ...
          ],
          "multiples_medians": {"EV/EBITDA": x, "P/E": x, "EV/CA": x},
          "valeur_multiples": x,
          "valeur_ev_ebitda": x,
          "valeur_p_e": x,
          "valeur_ev_ca": x
        }
        """,
        expected_output=(
            "JSON avec comparables_proposes, multiples_medians et valeur_multiples."
        ),
        agent=agent_comparables,
        context=[tache_collecte]
    )

    crew_phase1 = Crew(
        agents=[agent_collecteur, agent_analyste, agent_comparables],
        tasks=[tache_collecte, tache_dcf, tache_comparables],
        process=Process.sequential,
        verbose=False
    )

    return tache_collecte, tache_dcf, tache_comparables, crew_phase1


def lancer_phase2(
    resultat_dcf: str,
    resultat_multiples_valide: str,
    dette_nette: float,
    nombre_actions: float,
    poids_dcf: float = 0.60

):
    """
    Phase 2 : Critique → Agrégateur → Synthèse
    Reçoit les comparables validés par l'utilisateur.
    """

    agent_critique   = creer_agent_critique()
    agent_agregateur = creer_agent_agregateur()
    agent_synthese   = creer_agent_synthese()

    poids_multiples = round(1 - poids_dcf, 2)

    tache_critique = Task(
        description=f"""
        Audite les résultats du DCF et des Multiples.

        Résultat DCF reçu :
        {resultat_dcf}

        Résultat Multiples (validé par l'utilisateur) :
        {resultat_multiples_valide}

        IMPORTANT : si valeur_multiples = 0 ou comparables_proposes est vide,
        cela signifie que l'utilisateur n'a retenu aucun comparable.
        Dans ce cas, valide directement le DCF seul sans vérifier l'écart entre méthodes.
        Applique uniquement la vérification de la Valeur Terminale (seuil 85%).

        Sinon appelle auditer_resultats() normalement.
        Maximum {MAX_ITERATIONS} itérations.
        """,
        expected_output=(
            "JSON avec statut VALIDE/BLOQUÉ/FORCE_VALIDATION, "
            "problèmes identifiés et corrections chiffrées."
        ),
        agent=agent_critique
    )

    tache_agregation = Task(
        description=f"""
        Agrège les résultats validés par le critique.

        Appelle agreger_valorisation() avec :
          - resultat_dcf          : {resultat_dcf}
          - resultat_multiples    : {resultat_multiples_valide}
          - dette_nette           : {dette_nette}
          - nombre_actions        : {nombre_actions}
          - poids_dcf             : {poids_dcf}
          - poids_multiples       : {poids_multiples}

        Retourne le JSON complet avec fourchette et valeur par action.
        """,
        expected_output=(
            "JSON complet avec fourchette de valorisation, "
            "valeur par action et composition."
        ),
        agent=agent_agregateur,
        context=[tache_critique]
    )

    tache_synthese = Task(
        description=f"""
        Produis le rapport final et sauvegarde-le via sauvegarder_rapport().
        "Toutes les valeurs sont en kMAD. "
        "Convertis en M MAD (divise par 1000) pour le rapport final. "
        "Ex: 4_303_559 kMAD = 4 304 M MAD"
        


        Structure obligatoire :

        ═══════════════════════════════════════════════
        Date : {{date du jour}}        
        ═══════════════════════════════════════════════

        1. VALEUR D'ENTREPRISE
        ───────────────────────────────────────────────
        Méthode DCF         : [VE_DCF] kMAD  (pondération [X]%)
        Méthode Multiples   : [VE_Mult] kMAD  (pondération [X]%)
        Valeur centrale     : [VE_centrale] kMAD

        2. FOURCHETTE DE VALORISATION
        ───────────────────────────────────────────────
        Pessimiste : [VE_pess] kMAD 
        Central    : [VE_cent] kMAD
        Optimiste  : [VE_opti] kMAD 

        3. PARAMÈTRES CLÉS
        ───────────────────────────────────────────────
        WACC                : [wacc]%
        Taux croissance CT  : [taux_ct]%
        Taux croissance LT  : [taux_lt]%
        % Valeur Terminale  : [pct_terminal]%
        FCF projetés        : [fcf_forecast]

        4. COMPARABLES RETENUS
        ───────────────────────────────────────────────
        [Liste des comparables validés avec leurs multiples]

        5. AUDIT QUALITÉ
        ───────────────────────────────────────────────
        Statut critique     : [VALIDE / FORCE_VALIDATION]
        Itérations          : [n]
        Écart DCF/Multiples : [ecart]%

        6. COMMENTAIRES & RISQUES
        ───────────────────────────────────────────────
        [Analyse des hypothèses, limites, risques sectoriels]

        7. RECOMMANDATION
        ───────────────────────────────────────────────
        [Conclusion en 3-4 phrases]
        ═══════════════════════════════════════════════
        
        
        """,
        expected_output="Confirmation que le rapport est sauvegardé.",
        agent=agent_synthese,
        context=[tache_critique, tache_agregation]
    )

    crew_phase2 = Crew(
        agents=[agent_critique, agent_agregateur, agent_synthese],
        tasks=[tache_critique, tache_agregation, tache_synthese],
        process=Process.sequential,
        verbose=False,
        cache=False
    )

    return tache_critique, tache_agregation, tache_synthese, crew_phase2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python main.py <fichier> [poids_dcf] [mode]")
        sys.exit(1)

    file_path = sys.argv[1]
    poids_dcf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.60
    mode      = sys.argv[3]        if len(sys.argv) > 3 else "libre"

    print(f"\n{'='*55}")
    print(f"  Évaluation : {file_path}")
    print(f"  Mode       : {mode}")
    print(f"  Pondération: DCF {poids_dcf:.0%} / Multiples {1-poids_dcf:.0%}")
    print(f"{'='*55}\n")

    # Phase 1
    _, _, _, crew1 = lancer_phase1(file_path, mode)
    result1 = crew1.kickoff()
    print("\n✅ Phase 1 terminée — comparables à valider manuellement\n")