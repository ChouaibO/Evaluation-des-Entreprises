import json
from crewai import Agent
from crewai.tools import tool
from tools.calcul_dcf import DCFModel


@tool("Projeter les FCF futurs")
def projeter_fcf(
    ebit_historique: str,
    da_historique: str,
    capex_historique: str,
    bfr_historique: str,
    taux_is: float,
    taux_croissance: float
) -> str:
    """
    Projette les FCF sur 5 ans à partir des données historiques.
    Passer les listes en JSON string ex: '[100, 120, 140]'
    """
    try:
        fcf = DCFModel.projeter_fcf(
            ebit_historique  = json.loads(ebit_historique),
            da_historique    = json.loads(da_historique),
            capex_historique = json.loads(capex_historique),
            bfr_historique   = json.loads(bfr_historique),
            taux_is          = taux_is,
            taux_croissance  = taux_croissance
        )
        return json.dumps({"fcf_projetes": fcf})
    except Exception as e:
        return json.dumps({"erreur": str(e)})


@tool("Calculer le WACC")
def calculer_wacc(
    cout_dette: float,
    taux_is: float,
    dette_nette: float,
    capitaux_propres: float,
    beta: float,
    taux_sans_risque: float = 0.038,
    prime_risque_marche: float = 0.065
) -> str:
    """Calcule le WACC par le CAPM. Beta estimé selon secteur si non fourni."""
    try:
        result = DCFModel.calcul_wacc(
            cout_dette, taux_is, dette_nette,
            capitaux_propres, beta,
            taux_sans_risque, prime_risque_marche
        )
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"erreur": str(e)})


@tool("Calculer la valeur d'entreprise DCF")
def calculer_dcf(fcf_forecast: str, wacc: float, terminal_growth: float) -> str:
    """
    Calcule la valeur d'entreprise par DCF.
    fcf_forecast : liste JSON des FCF projetés sur 5 ans.
    Retourne VE, VA FCF, VA terminale et % valeur terminale.
    """
    try:
        fcf_list = json.loads(fcf_forecast) if isinstance(fcf_forecast, str) else fcf_forecast
        result = DCFModel.enterprise_value(fcf_list, wacc, terminal_growth)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"erreur": str(e)})


def creer_agent_analyste():
    return Agent(
        role="Analyste financier DCF",
        goal=(
            "Construire un modèle DCF rigoureux en trois étapes : "
            "1) Calculer le WACC via calculer_wacc(), "
            "2) Projeter les FCF via projeter_fcf(), "
            "3) Calculer la VE via calculer_dcf(). "
            "Estimer les paramètres manquants (beta, taux sans risque) "
            "selon les références du marché marocain. "
            "Retourner un JSON structuré avec tous les résultats."
        ),
        backstory=(
            "Tu es spécialiste DCF pour le marché marocain. "
            "Tu justifies chaque hypothèse (beta sectoriel, prime de risque). "
            "Tu n'effectues jamais de calcul toi-même — tu appelles toujours les outils. "
            "Si le taux de croissance n'est pas fourni, tu l'estimes à partir "
            "du TCAM historique du CA et du contexte sectoriel marocain."
        ),
        tools=[calculer_wacc, projeter_fcf, calculer_dcf],
        llm="azure/gpt-4.1-nano",
        verbose=True
    )