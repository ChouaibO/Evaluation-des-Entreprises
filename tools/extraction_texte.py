#extraction_texte.py
"""
-------------------
Lit les fichiers PDF / Excel / TXT et valide que leur contenu
contient des données financières exploitables.

Deux chemins possibles :
  A) Fichier libre  (PDF, TXT, Excel quelconque)
       → lire + valider la présence de données financières minimales
       → lever DocumentNonExploitable si le contenu est insuffisant

  B) Template officiel  (Excel respectant le template de l'application)
       → lire + valider la conformité au template
       → lever TemplateNonConforme si des champs obligatoires manquent
"""

from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd
import pdfplumber

# ── Constantes de validation ──────────────────────────────────────────────────

# Champs minimaux pour qu'un document libre soit jugé "exploitable"
CHAMPS_MINIMAUX = {
    "chiffre_affaires": [
        "chiffre d'affaires", "ca", "revenus", "revenues", "turnover", "ventes"
    ],
    "resultat_exploitation": [
        "ebit", "résultat d'exploitation", "resultat d exploitation",
        "résultat opérationnel", "operating income"
    ],
    "capitaux_propres": [
        "capitaux propres", "fonds propres", "equity", "situation nette"
    ],
    "dette": [
        "dette", "dettes financières", "emprunts", "borrowings",
        "financial debt", "endettement"
    ],
}

# Seuil : le document est exploitable si au moins N champs minimaux sont détectés
SEUIL_CHAMPS = 3

# Mots-clés financiers génériques (pour filtrer les pages PDF pertinentes)
MOTS_CLES_FINANCIERS = [
    "ebit", "résultat", "chiffre d'affaires", "capex",
    "amortissement", "trésorerie", "capitaux propres", "bilan",
    "cpc", "cash flow", "dette", "ebitda", "ebe", "marge",
    "revenus", "charges", "impôt", "résultat net"
]

# Colonnes attendues dans le template officiel (feuille "Données Financières")
TEMPLATE_SHEET = "Données Financières"
TEMPLATE_COLONNES_OBLIGATOIRES = [
    "chiffre d'affaires",
    "résultat net",
    "capitaux propres",
    "dettes financières",
]


def detecter_unite_et_normaliser(valeur: float, texte_contexte: str) -> float:
    """
    Détecte l'unité depuis le contexte et retourne la valeur en MAD.
    """
    texte = texte_contexte.lower()

    if "mmad" in texte or "millions" in texte or "m mad" in texte:
        return valeur * 1_000_000
    elif "kmad" in texte or "milliers" in texte or "k mad" in texte:
        return valeur * 1_000
    elif "mrd" in texte or "milliards" in texte or "md mad" in texte:
        return valeur * 1_000_000_000
    else:
        return valeur  # déjà en MAD

# ── Exceptions personnalisées ─────────────────────────────────────────────────

class DocumentNonExploitable(Exception):
    """Levée quand un fichier libre ne contient pas assez de données financières."""


class TemplateNonConforme(Exception):
    """Levée quand le fichier Excel ne respecte pas le template officiel."""


# ── Classe principale ─────────────────────────────────────────────────────────

class ExtractionTexte:
    """
    Interface unifiée pour lire et valider les fichiers financiers.

    Usage :
        # Fichier libre
        contenu = ExtractionTexte.read(path)

        # Template officiel
        contenu = ExtractionTexte.read_template(path)
    """

    # ── Chemin A : fichier libre ──────────────────────────────────────────

    @staticmethod
    def read(file_path: str) -> str:
        """
        Lit un fichier PDF, Excel ou TXT.
        Valide la présence de données financières minimales.
        Lève DocumentNonExploitable si le contenu est insuffisant.
        """
        extension = os.path.splitext(file_path)[1].lower()

        if extension == ".pdf":
            contenu = ExtractionTexte._lire_pdf(file_path)
        elif extension == ".txt":
            contenu = ExtractionTexte._lire_txt(file_path)
        elif extension in [".xlsx", ".xls"]:
            contenu = ExtractionTexte._lire_excel_libre(file_path)
        else:
            raise ValueError(
                f"Format non supporté : '{extension}'. "
                "Formats acceptés : PDF, TXT, XLSX, XLS."
            )

        # Validation du contenu extrait
        champs_trouves = ExtractionTexte._detecter_champs(contenu)
        if len(champs_trouves) < SEUIL_CHAMPS:
            manquants = [
                c for c in CHAMPS_MINIMAUX if c not in champs_trouves
            ]
            raise DocumentNonExploitable(
                f"Le document ne contient pas assez de données financières "
                f"exploitables.\n"
                f"Champs détectés ({len(champs_trouves)}/{len(CHAMPS_MINIMAUX)}) : "
                f"{', '.join(champs_trouves) or 'aucun'}.\n"
                f"Champs manquants ou non reconnus : {', '.join(manquants)}.\n\n"
                "→ Vérifiez que le document contient au minimum : "
                "Chiffre d'affaires, EBIT, Capitaux propres, Dettes financières.\n"
                "→ Ou utilisez le template Excel officiel disponible en téléchargement."
            )

        return contenu

    # ── Chemin B : template officiel ─────────────────────────────────────

    @staticmethod
    def read_template(file_path: str) -> dict[str, Any]:
        """
        Lit un fichier Excel conforme au template officiel.
        Retourne un dictionnaire structuré des données extraites.
        Lève TemplateNonConforme si la structure est incorrecte.
        """
        extension = os.path.splitext(file_path)[1].lower()
        if extension not in [".xlsx", ".xls"]:
            raise TemplateNonConforme(
                "Le template officiel doit être un fichier Excel (.xlsx)."
            )

        try:
            xl = pd.ExcelFile(file_path)
        except Exception as e:
            raise TemplateNonConforme(f"Impossible d'ouvrir le fichier Excel : {e}")

        if TEMPLATE_SHEET not in xl.sheet_names:
            raise TemplateNonConforme(
                f"La feuille '{TEMPLATE_SHEET}' est absente du fichier.\n"
                "Assurez-vous d'utiliser le template officiel téléchargé depuis la plateforme."
            )

        df = pd.read_excel(file_path, sheet_name=TEMPLATE_SHEET, header=None)
        donnees = ExtractionTexte._parser_template(df)

        # Validation des champs obligatoires du template
        manquants = []
        for champ in TEMPLATE_COLONNES_OBLIGATOIRES:
            if not any(champ in k.lower() for k in donnees.keys()):
                manquants.append(champ)

        if manquants:
            raise TemplateNonConforme(
                f"Champs obligatoires manquants dans le template : "
                f"{', '.join(manquants)}.\n"
                "Veuillez compléter le template avant de le soumettre."
            )

        return donnees

    # ── Lecteurs internes ─────────────────────────────────────────────────

    @staticmethod
    def _lire_pdf(file_path: str) -> str:
        pages_pertinentes = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                texte = page.extract_text()
                if texte and any(
                    mot.lower() in texte.lower()
                    for mot in MOTS_CLES_FINANCIERS
                ):
                    pages_pertinentes.append(texte)

        if not pages_pertinentes:
            raise DocumentNonExploitable(
                "Aucune page financière détectée dans le PDF. "
                "Le document ne semble pas contenir de données comptables ou financières."
            )

        return "\n".join(pages_pertinentes)

    @staticmethod
    def _lire_txt(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def _lire_excel_libre(file_path: str) -> str:
        """Lit un Excel quelconque (non-template) et retourne son contenu texte."""
        try:
            xl = pd.ExcelFile(file_path)
            parties = []
            for sheet in xl.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet)
                parties.append(f"=== Feuille : {sheet} ===\n{df.to_string()}")
            return "\n\n".join(parties)
        except Exception as e:
            raise ValueError(f"Erreur de lecture Excel : {e}")

    # ── Détection de champs ───────────────────────────────────────────────

    @staticmethod
    def _detecter_champs(contenu: str) -> list[str]:
        """
        Détecte quels champs financiers minimaux sont présents dans le contenu.
        Retourne la liste des champs détectés.
        """
        contenu_lower = contenu.lower()
        detectes = []
        for champ, synonymes in CHAMPS_MINIMAUX.items():
            if any(re.search(r'\b' + re.escape(s) + r'\b', contenu_lower)
                   for s in synonymes):
                detectes.append(champ)
        return detectes

    # ── Parseur template ──────────────────────────────────────────────────

    @staticmethod
    def _parser_template(df: pd.DataFrame) -> dict[str, Any]:
        """
        Extrait les données du template Excel sous forme de dictionnaire.
        Structure : { "label_ligne": {"N-3": val, "N-2": val, "N-1": val,
                                       "taux_croissance": val | None, ...} }
        """
        ANNEES = ["N-3", "N-2", "N-1", "N+1", "N+2", "N+3", "N+4", "N+5"]

        # Trouver la ligne d'en-tête des années
        header_row = None
        col_annees: dict[str, int] = {}

        for i, row in df.iterrows():
            for j, val in enumerate(row):
                if str(val).strip() in ANNEES:
                    if header_row is None:
                        header_row = i
                    col_annees[str(val).strip()] = j

        if header_row is None or not col_annees:
            raise TemplateNonConforme(
                "Impossible de localiser les colonnes d'années dans le template. "
                "La structure du fichier a peut-être été modifiée."
            )

        donnees: dict[str, Any] = {}

        for i in range(header_row + 1, len(df)):
            row = df.iloc[i]
            label_brut = str(row.iloc[0]).strip()

            # Ignorer les lignes vides, titres de section, notices
            if not label_brut or label_brut in ("nan", "None"):
                continue
            if label_brut.startswith("🔵") or label_brut.startswith("=="):
                continue

            label = label_brut.lstrip(" •→").strip().lower()
            if not label:
                continue

            valeurs: dict[str, Any] = {}
            for annee, col_idx in col_annees.items():
                try:
                    v = row.iloc[col_idx]
                    valeurs[annee] = None if pd.isna(v) else v
                except IndexError:
                    valeurs[annee] = None

            # N'inclure que les lignes ayant au moins une valeur historique
            historique = [valeurs.get(a) for a in ["N-3", "N-2", "N-1"]
                          if valeurs.get(a) is not None]
            if historique:
                donnees[label] = valeurs

        return donnees