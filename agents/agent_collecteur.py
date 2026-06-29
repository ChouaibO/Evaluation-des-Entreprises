from crewai import Agent
from crewai.tools import tool
from tools.extraction_texte import ExtractionTexte, DocumentNonExploitable, TemplateNonConforme

@tool("Lire un document financier libre")
def lire_document_libre(file_path: str) -> str:
    """
    Lit un fichier PDF, Excel ou TXT et valide qu'il contient
    des données financières exploitables (CA, EBIT, Capitaux propres, Dettes).
    Rejette le document avec un message clair si insuffisant.
    """
    try:
        contenu = ExtractionTexte.read(file_path)
        return f"✅ Document exploitable. Contenu extrait :\n\n{contenu}"
    except DocumentNonExploitable as e:
        return f"❌ DOCUMENT REJETÉ — {e}"
    except ValueError as e:
        return f"❌ FORMAT NON SUPPORTÉ — {e}"
    except Exception as e:
        return f"❌ ERREUR DE LECTURE — {e}"


@tool("Lire le template Excel officiel")
def lire_template_excel(file_path: str) -> str:
    """
    Lit un fichier Excel conforme au template officiel de la plateforme.
    Valide la structure et retourne les données financières structurées.
    Rejette si le template est incomplet ou non conforme.
    """
    try:
        donnees = ExtractionTexte.read_template(file_path)
        lignes = [f"✅ Template conforme. Données extraites :\n"]
        for label, valeurs in donnees.items():
            vals_str = " | ".join(
                f"{annee}: {v}" for annee, v in valeurs.items() if v is not None
            )
            lignes.append(f"  • {label} → {vals_str}")
        return "\n".join(lignes)
    except TemplateNonConforme as e:
        return f"❌ TEMPLATE NON CONFORME — {e}"
    except Exception as e:
        return f"❌ ERREUR — {e}"


def creer_agent_collecteur():
    return Agent(
        role="Collecteur de données financières",
        goal=(
            "Lire le document soumis par l'utilisateur et extraire toutes "
            "les données financières disponibles. "
            "Utiliser 'Lire le template Excel officiel' si l'utilisateur a soumis "
            "le template officiel, sinon utiliser 'Lire un document financier libre'. "
            "Signaler clairement ce qui manque plutôt que d'inventer des données."
        ),
        backstory=(
            "Tu es expert en lecture de documents financiers marocains (CPC, bilan, "
            "états de flux). Tu sais distinguer un document exploitable d'un document "
            "vide ou hors sujet. Tu rejettes proprement les fichiers insuffisants "
            "avec un message explicatif utile à l'utilisateur."
        ),
        tools=[lire_document_libre, lire_template_excel],
        llm="azure/gpt-4.1-nano",
        verbose=True
    )