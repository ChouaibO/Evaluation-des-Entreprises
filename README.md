# Système Multi-Agent de valorisation des entreprises.




Plateforme d'évaluation financière d'entreprises marocaines combinant la méthode **DCF (Discounted Cash Flow)** et la méthode des **Multiples comparables**, orchestrée par un système multi-agents IA (CrewAI + LLM).

L'application lit un document financier (Option 2: document libre ou Option 1: template officiel à télécharger puis remplir manuellement), extrait et structure les données, construit un modèle DCF complet, recherche des comparables boursiers, audite la cohérence des résultats, puis génère un rapport de valorisation final.

---

## Table des matières

1. [Aperçu de l'architecture](#aperçu-de-larchitecture)
2. [Les agents du système](#les-agents-du-système)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Lancement de l'application](#lancement-de-lapplication)
6. [Guide d'utilisation (interface Streamlit)](#guide-dutilisation-interface-streamlit)
7. [Le template Excel officiel](#le-template-excel-officiel)
8. [Comprendre le rapport de sortie](#comprendre-le-rapport-de-sortie)
9. [Structure du projet](#structure-du-projet)
10. [Utilisation en ligne de commande](#utilisation-en-ligne-de-commande)

---

## Aperçu de l'architecture

Le processus d'évaluation se déroule en **deux phases**, séparées par un point de validation manuelle :

```
                    PHASE 1
┌─────────────────────────────────────────────────────────┐
│  Collecteur  →  Analyste DCF  →  Comparables Boursiers   │
│  (lecture)      (calcul VE)      (recherche multiples)   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              ⏸  VALIDATION UTILISATEUR  ⏸
        (l'utilisateur choisit les comparables
         à retenir parmi ceux proposés)
                          │
                          ▼
                    PHASE 2
┌─────────────────────────────────────────────────────────┐
│  Critique/Audit  →  Agrégateur  →  Rédacteur (Synthèse)  │
│  (contrôle qualité)  (pondération)  (rapport final)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
              📄 Rapport de valorisation final
```

Cette séparation en deux phases permet à l'utilisateur de garder le contrôle sur le choix des entreprises comparables avant que le système ne calcule la valorisation finale pondérée.

---

## Les agents du système

| Agent | Rôle | Outils principaux |
|---|---|---|
| **Collecteur** | Lit le document soumis (Excel, PDF, TXT) et extrait les données financières structurées | `lire_document_libre`, `lire_template_excel` |
| **Analyste DCF** | Calcule le WACC, projette les flux de trésorerie (FCF) et la valeur d'entreprise par DCF | `calculer_wacc`, `projeter_fcf`, `calculer_dcf` |
| **Comparables** | Recherche des entreprises cotées comparables et calcule la valorisation par multiples | `SerperDevTool` (recherche web), `calculer_multiples` |
| **Critique / Auditeur** | Vérifie la cohérence entre DCF et Multiples (écart max 30%) et le poids de la valeur terminale (max 85%) | `auditer_resultats` |
| **Agrégateur** | Combine DCF et Multiples selon la pondération choisie, calcule la fourchette pessimiste/centrale/optimiste et la valeur par action | `agreger_valorisation` |
| **Synthèse** | Rédige le rapport final structuré et le sauvegarde | `sauvegarder_rapport` |

Tous les agents utilisent le modèle **Azure GPT-4.1-nano** via LiteLLM.

---

## Installation

> ℹ️ L'installation ci-dessous est utile uniquement pour faire tourner le projet **en local** (développement, contribution, débogage). Pour une simple utilisation, voir le lien de l'application déployée en haut de ce document.

### Prérequis

- Python 3.10 ou supérieur
- Un compte Azure OpenAI (ou équivalent compatible LiteLLM) avec un déploiement GPT-4.1-nano
- Une clé API [Serper.dev](https://serper.dev) pour la recherche de comparables boursiers

### Étapes

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd Evaluation-des-Entreprises

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt
```

### Dépendances principales

| Package | Usage |
|---|---|
| `crewai` | Orchestration multi-agents |
| `crewai-tools` | Outils intégrés (recherche web via Serper) |
| `litellm` | Connecteur LLM (Azure OpenAI) |
| `streamlit` | Interface utilisateur web |
| `pandas` | Lecture et traitement des fichiers Excel |
| `openpyxl` | Génération du template Excel officiel |
| `pdfplumber` | Extraction de texte depuis les PDF |
| `plotly` | Graphiques interactifs dans l'interface |
| `python-dotenv` | Gestion des variables d'environnement |

---

## Configuration

Créer un fichier `.env` à la racine du projet :

```env
# Azure OpenAI
AZURE_API_KEY=votre_cle_azure
AZURE_API_BASE=https://votre-ressource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview

# Recherche de comparables boursiers
SERPER_API_KEY=votre_cle_serper
```

> **Important :** ne jamais committer le fichier `.env`. Vérifier qu'il figure bien dans `.gitignore`.

### Configuration sur Streamlit Community Cloud

En production, les variables ci-dessus ne sont pas lues depuis `.env` mais depuis les **Secrets** de l'application, configurables dans le tableau de bord Streamlit Cloud (`Settings → Secrets`), au format TOML :

```toml
AZURE_API_KEY = "votre_cle_azure"
AZURE_API_BASE = "https://votre-ressource.openai.azure.com/"
AZURE_API_VERSION = "2024-02-15-preview"
SERPER_API_KEY = "votre_cle_serper"
```

---

## Lancement de l'application

### En ligne (déployé sur Streamlit Community Cloud)

L'application est accessible directement depuis le lien ci-dessus, sans installation. Il suffit de déposer un document financier et de suivre le [guide d'utilisation](#guide-dutilisation-interface-streamlit).

### En local (développement)

```bash
streamlit run app.py
```

L'application s'ouvre automatiquement dans le navigateur à l'adresse `http://localhost:8501`.

### Ligne de commande

```bash
python main.py <chemin_fichier> [poids_dcf] [mode]
```

Voir la section [Utilisation en ligne de commande](#utilisation-en-ligne-de-commande) pour le détail des arguments.

---

## Guide d'utilisation (interface Streamlit)

### Étape 1 — Déposer le document financier

Deux modes de soumission sont proposés :

- **Template Excel officiel** : fichier Excel structuré selon le format de la plateforme (voir [section dédiée](#le-template-excel-officiel)). Recommandé pour une extraction fiable à 100%.
- **Fichier quelconque** : Excel, PDF ou TXT contenant des données financières (compte de résultat, bilan), sans structure imposée. L'IA tente d'en extraire les informations nécessaires.

Le document doit contenir au minimum : chiffre d'affaires, résultat d'exploitation (EBIT), capitaux propres et niveau d'endettement. À défaut, le document est rejeté avec un message explicatif.

### Étape 2 — Régler la pondération DCF / Multiples

Un curseur permet de définir le poids accordé à chaque méthode dans le calcul de la valeur finale (par défaut : 60% DCF / 40% Multiples). Cette pondération s'applique uniquement si des comparables sont retenus ; en leur absence, le DCF est utilisé à 100%.

### Étape 3 — Lancer l'évaluation (Phase 1)

Cliquer sur **« Démarrer l'évaluation »**. Le système exécute séquentiellement :

1. Lecture et extraction des données du document
2. Construction du modèle DCF (WACC, projection des FCF, valeur d'entreprise)
3. Recherche de comparables boursiers et calcul des multiples

### Étape 4 — Valider les comparables proposés

L'agent Comparables propose entre 1 et 3 entreprises cotées du même secteur (priorité Bourse de Casablanca, puis MENA, puis Europe). L'utilisateur peut :

- accepter tout ou partie des comparables proposés,
- les écarter entièrement (le système basculera alors sur une valorisation DCF pure).

Tout multiple jugé aberrant (EV/EBITDA > 20x ou négatif) est signalé explicitement par l'agent.

### Étape 5 — Finaliser (Phase 2)

Une fois les comparables validés, le système enchaîne :

1. **Audit** des résultats DCF et Multiples (cohérence, poids de la valeur terminale)
2. **Agrégation** pondérée en valeur d'entreprise, valeur des capitaux propres et valeur par action
3. **Rédaction** du rapport final structuré, sauvegardé automatiquement

### Étape 6 — Consulter les résultats

L'interface affiche :

- les **indicateurs clés** (valeur centrale, scénarios pessimiste/optimiste, WACC),
- des **graphiques interactifs** (comparaison des méthodes, décomposition de la valeur, fourchette de scénarios),
- le **rapport complet** téléchargeable, incluant les paramètres retenus, les comparables validés, le statut de l'audit qualité et la recommandation finale.

---

## Le template Excel officiel

Pour garantir une extraction fiable des données, la plateforme propose un template Excel téléchargeable, généré via `tools/template_excel.py`.

### Structure du template

| Feuille | Contenu |
|---|---|
| **Données Financières** | Compte de résultat, bilan, flux de trésorerie, paramètres WACC, taux de croissance et informations générales, sur 3 années historiques (N-3 à N-1) et 5 années de projection (N+1 à N+5) |
| **Notice & Instructions** | Règles de saisie, unités, gestion des champs optionnels |

### Code couleur

- 🔵 **Cellules bleues** : saisie obligatoire (historique N-3 à N-1)
- 🟡 **Cellules jaunes** : optionnelles — estimées automatiquement par l'agent si laissées vides (paramètres WACC, taux de croissance)
- 🟢 **Cellules vertes** : projections calculées automatiquement par l'agent (N+1 à N+5)

### Génération du template

```python
from tools.template_excel import generer_template

chemin = generer_template("template_evaluation.xlsx")
```

---

## Comprendre le rapport de sortie

Le rapport final, sauvegardé dans `outputs/rapport_valorisation.txt` (et archivé avec horodatage), comprend sept sections :

1. **Valeur d'entreprise** — résultats des deux méthodes et valeur centrale pondérée
2. **Fourchette de valorisation** — scénarios pessimiste / central / optimiste
3. **Paramètres clés** — WACC, taux de croissance court terme et terminal, poids de la valeur terminale, FCF projetés
4. **Comparables retenus** — liste des entreprises comparables validées avec leurs multiples
5. **Audit qualité** — statut de validation (VALIDE / FORCE_VALIDATION), nombre d'itérations, écart entre méthodes
6. **Commentaires & risques** — limites du modèle, hypothèses retenues, risques sectoriels
7. **Recommandation** — synthèse et conclusion actionnable

Toutes les valeurs monétaires sont exprimées en dirhams marocains (MAD), avec un format d'affichage adapté à l'ordre de grandeur (k MAD, M MAD ou Md MAD).

---

## Structure du projet

```
Evaluation-des-Entreprises/
├── app.py                          # Interface Streamlit
├── main.py                         # Orchestration CrewAI (phases 1 et 2)
├── agents/
│   ├── agent_collecteur.py         # Lecture et extraction des données
│   ├── agent_analyste.py           # Modèle DCF (WACC, FCF, VE)
│   ├── agent_comparable.py         # Recherche et calcul par multiples
│   ├── agent_critique.py           # Audit de cohérence
│   ├── agent_agregateur.py         # Pondération et fourchette finale
│   └── agent_synthese.py           # Rédaction du rapport
├── tools/
│   ├── calcul_dcf.py               # Logique financière du modèle DCF
│   ├── extraction_texte.py         # Lecture PDF / Excel / TXT
│   └── template_excel.py           # Génération du template Excel officiel
├── outputs/                        # Rapports et résultats générés
├── .env                            # Variables d'environnement (non versionné)
└── requirements.txt
```

---

## Utilisation en ligne de commande

```bash
python main.py <fichier> [poids_dcf] [mode]
```

| Argument | Description | Valeur par défaut |
|---|---|---|
| `fichier` | Chemin vers le document à évaluer (obligatoire) | — |
| `poids_dcf` | Pondération du DCF dans la valeur finale (entre 0 et 1) | `0.60` |
| `mode` | `template` pour le template officiel, `libre` pour un document quelconque | `libre` |

### Exemple

```bash
python main.py data/entreprise.xlsx 0.70 template
```

Cette commande lance la Phase 1 (collecte, DCF, comparables) avec une pondération de 70% DCF / 30% Multiples, en utilisant le parseur du template officiel. La Phase 1 s'arrête après la proposition des comparables, en attente de validation — la Phase 2 doit être lancée séparément une fois les comparables choisis.

---

## Notes complémentaires

- **Devise** : toutes les données sont normalisées et traitées en dirhams marocains (MAD) brut tout au long du pipeline, quelle que soit l'unité d'origine du document soumis (MAD, kMAD, MMAD, Md MAD).
- **Limites d'itération** : l'agent Critique dispose d'un maximum de 3 itérations de correction avant validation forcée des résultats, avec mention explicite dans le rapport.
- **Seuils de contrôle qualité** : écart maximal toléré entre DCF et Multiples de 30% ; poids maximal de la valeur terminale de 85% de la valeur DCF.

