import os
import json
import tempfile
import re
import time
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

# ── CONFIG PAGE ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Évaluation Entreprise",
    page_icon="📊",
    layout="wide"
)

# ── STYLE ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    .stButton > button {
        width: 100%;
        background-color: #1A3A6B;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px;
        font-weight: 500;
    }
    .stButton > button:hover { background-color: #2A5AA0; }
    .kpi-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        background: #f9f9f9;
    }
    .kpi-label { font-size: 12px; color: #888; margin-bottom: 4px; }
    .kpi-value { font-size: 22px; font-weight: 700; color: #1A3A6B; }
    .critique-ok   { background: #e8f5e9; border-left: 4px solid #3B6D11; padding: 10px; border-radius: 6px; }
    .critique-warn { background: #fff8e1; border-left: 4px solid #F57F17; padding: 10px; border-radius: 6px; }
    .critique-block{ background: #fdecea; border-left: 4px solid #A32D2D; padding: 10px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


# ── SESSION STATE — initialisation unique ─────────────────────────────────────
def _init_state():
    defaults = {
        "etapes": {
            "collecteur":  False,
            "analyste":    False,
            "comparables": False,
            "critique":    False,
            "agregateur":  False,
            "synthese":    False,
        },
        "rapport_pret":       False,
        "resultats_json":     None,   # dict agrégé sauvegardé par l'agrégateur
        "comparables_json":   None,   # liste des comparables pour validation
        "critique_statut":    None,   # "VALIDE" | "BLOQUE" | "FORCE_VALIDATION"
        "critique_iterations": 0,
        "poids_dcf":          0.60,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── UTILITAIRES ───────────────────────────────────────────────────────────────

def extraire_nombre(texte: str, mots_cles: list):
    for mot in mots_cles:
        pattern = rf"{mot}[\s:=]*([+-]?[\d\s.,]+)"
        match = re.search(pattern, texte, re.IGNORECASE)
        if match:
            val = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return float(val)
            except ValueError:
                continue
    return None


def parser_resultats(texte: str) -> dict:
    """Extrait les valeurs numériques clés du rapport final (fallback texte)."""
    return {
        "valeur_entreprise": extraire_nombre(texte, [
            r"valeur centrale", r"valeur d.entreprise", r"enterprise.value"
        ]),
        "wacc":           extraire_nombre(texte, [r"wacc"]),
        "taux_croissance":extraire_nombre(texte, [r"taux de croissance terminal", r"terminal.growth"]),
        "pct_terminal":   extraire_nombre(texte, [r"% valeur terminale", r"pct.terminal"]),
        "pessimiste":     extraire_nombre(texte, [r"pessimiste"]),
        "central":        extraire_nombre(texte, [r"central\b"]),
        "optimiste":      extraire_nombre(texte, [r"optimiste"]),
        "vpa_centrale":   extraire_nombre(texte, [r"valeur.par.action.*centrale", r"vpa.*central"]),
    }


def charger_resultats_json() -> dict | None:
    """Lit le fichier JSON produit par l'agrégateur s'il existe."""
    path = "outputs/resultats_agregation.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def formater_mad(valeur):
    """Valeur reçue en MAD."""
    if valeur is None:
        return "N/A"
    if abs(valeur) >= 1_000_000_000:
        return f"{valeur / 1_000_000_000:.2f} Md MAD"
    if abs(valeur) >= 1_000_000:
        return f"{valeur / 1_000_000:.1f} M MAD"
    if abs(valeur) >= 1_000:
        return f"{valeur / 1_000:.1f} k MAD"
    return f"{valeur:,.0f} MAD"
# ── GRAPHIQUES ────────────────────────────────────────────────────────────────

def graphique_fcf(fcf_list: list):
    annees = [f"N+{i+1}" for i in range(len(fcf_list))]
    fig = go.Figure(go.Bar(
        x=annees,
        y=[f / 1_000 for f in fcf_list],   # kMAD → MMAD
        marker_color=["#1A3A6B", "#2A5AA0", "#3A7AD0", "#4A9AE0", "#5AAAF0"],
        text=[f"{f/1_000:.0f} M" for f in fcf_list],
        textposition="outside"
    ))
    fig.update_layout(
        title="FCF Projetés N+1 → N+5 (M MAD)",
        yaxis_title="Millions MAD",
        plot_bgcolor="white", height=320,
        margin=dict(t=40, b=20)
    )
    return fig


def graphique_decomposition(va_fcf: float, va_terminale: float):
    fig = go.Figure(go.Pie(
        labels=["VA des FCF", "VA Valeur Terminale"],
        values=[va_fcf, va_terminale],
        marker_colors=["#1A3A6B", "#5AAAF0"],
        hole=0.4, textinfo="label+percent"
    ))
    fig.update_layout(
        title="Décomposition de la Valeur DCF",
        height=320, margin=dict(t=40, b=20)
    )
    return fig


def graphique_scenarios(pessimiste: float, central: float, optimiste: float):
    fig = go.Figure(go.Bar(
        x=[v / 1_000_000 for v in [pessimiste, central, optimiste]],
        y=["Pessimiste", "Central", "Optimiste"],
        orientation="h",
        marker_color=["#A32D2D", "#1A3A6B", "#3B6D11"],
        text=[formater_mad(v) for v in [pessimiste, central, optimiste]],
        textposition="outside"
    ))
    fig.update_layout(
        title="Fourchette de Valorisation",
        xaxis_title="Millions MAD",
        plot_bgcolor="white", height=280,
        margin=dict(t=40, b=20)
    )
    return fig


def graphique_waterfall(va_fcf: float, va_terminale: float, dette_nette: float = 0):
    fig = go.Figure(go.Waterfall(
        x=["VA FCF", "VA Terminale", "Dette nette", "Valeur CP"],
        measure=["relative", "relative", "relative", "total"],
        y=[va_fcf/1_000, va_terminale/1_000, -dette_nette/1_000, 0],
        increasing=dict(marker=dict(color="#1A3A6B")),
        decreasing=dict(marker=dict(color="#A32D2D")),
        totals=dict(marker=dict(color="#3B6D11")),
        text=[
            formater_mad(va_fcf),
            formater_mad(va_terminale),
            f"-{formater_mad(dette_nette)}",
            ""
        ],
        textposition="outside",
        connector=dict(line=dict(color="rgb(63, 63, 63)"))
    ))
    fig.update_layout(
        title="Du DCF à la Valeur des Capitaux Propres",
        yaxis_title="Millions MAD",
        plot_bgcolor="white",
        height=320,
        margin=dict(t=40, b=20)
    )
    return fig


def graphique_comparaison_methodes(ve_dcf: float, ve_mult: float, ve_finale: float):
    fig = go.Figure(go.Bar(
        x=["DCF", "Multiples", "Valeur finale"],
        y=[ve_dcf/1_000, ve_mult/1_000, ve_finale/1_000],
        marker_color=["#1A3A6B", "#3A7AD0", "#3B6D11"],
        text=[formater_mad(v) for v in [ve_dcf, ve_mult, ve_finale]],
        textposition="outside"
    ))
    fig.update_layout(
        title="DCF vs Multiples vs Valeur Finale",
        yaxis_title="Millions MAD",
        plot_bgcolor="white", height=300,
        margin=dict(t=40, b=20)
    )
    return fig


# ── LANCEMENT AGENTS ──────────────────────────────────────────────────────────

# ── LANCEMENT PHASE 1 ─────────────────────────────────────────────────────────
def lancer_phase1_ui(chemin: str, mode: str):
    """Lance collecteur + DCF + comparables et sauvegarde les résultats."""
    from main import lancer_phase1

    tache_collecte, tache_dcf, tache_comparables, crew = lancer_phase1(chemin, mode)

    def apres_collecte(output):
        st.session_state.etapes["collecteur"] = True

    def apres_dcf(output):
        st.session_state.etapes["analyste"] = True
        # Sauvegarde résultat DCF pour la phase 2
        try:
            st.session_state.resultat_dcf = str(output)
        except Exception:
            pass

    def apres_comparables(output):
        st.session_state.etapes["comparables"] = True
        try:
            texte = str(output)

            # Cherche tous les blocs JSON et prend le plus grand
            import re
            blocs = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', texte, re.DOTALL)

            data = None
            for bloc in sorted(blocs, key=len, reverse=True):
                try:
                    parsed = json.loads(bloc)
                    if "comparables_proposes" in parsed:
                        data = parsed
                        break
                except Exception:
                    continue

            if data:
                st.session_state.comparables_json = data.get("comparables_proposes") or []
                st.session_state.resultat_multiples = json.dumps(data)
            else:
                # Dernier recours : construire manuellement depuis le texte
                noms = re.findall(r'"nom"\s*:\s*"([^"]+)"', texte)
                ev_ebitdas = re.findall(r'"ev_ebitda"\s*:\s*([\d.]+)', texte)
                pes = re.findall(r'"pe"\s*:\s*([\d.]+)', texte)

                if noms:
                    comparables = []
                    for i, nom in enumerate(noms):
                        comparables.append({
                            "nom": nom,
                            "ev_ebitda": float(ev_ebitdas[i]) if i < len(ev_ebitdas) else 0,
                            "pe": float(pes[i]) if i < len(pes) else 0,
                            "aberrant": False
                        })
                    st.session_state.comparables_json = comparables
                    st.session_state.resultat_multiples = json.dumps({
                        "comparables_proposes": comparables
                    })
                else:
                    st.session_state.comparables_json = []
                    st.session_state.resultat_multiples = texte

        except Exception:
            st.session_state.comparables_json = []
            st.session_state.resultat_multiples = str(output)


    tache_collecte.callback   = apres_collecte
    tache_dcf.callback        = apres_dcf
    tache_comparables.callback= apres_comparables

    crew.kickoff()
    st.session_state.phase1_terminee = True


# ── LANCEMENT PHASE 2 ─────────────────────────────────────────────────────────
def lancer_phase2_ui(poids_dcf: float):
    from main import lancer_phase2
    import statistics

    comparables_valides = st.session_state.get("comparables_valides") or []
    resultat_multiples  = st.session_state.get("resultat_multiples") or "{}"

    if comparables_valides:
        ev_ebitda_vals = [c["ev_ebitda"] for c in comparables_valides if not c.get("aberrant") and c.get("ev_ebitda")]
        pe_vals        = [c["pe"]        for c in comparables_valides if not c.get("aberrant") and c.get("pe")]
        ev_ca_vals     = [c["ev_ca"]     for c in comparables_valides if not c.get("aberrant") and c.get("ev_ca")]

        multiples_medians = {
            "EV/EBITDA": statistics.median(ev_ebitda_vals) if ev_ebitda_vals else 0,
            "P/E":       statistics.median(pe_vals)        if pe_vals        else 0,
            "EV/CA":     statistics.median(ev_ca_vals)     if ev_ca_vals     else 0,
        }
        try:
            data = json.loads(resultat_multiples)
            data["comparables_proposes"] = comparables_valides
            data["multiples_medians"]    = multiples_medians
            resultat_multiples = json.dumps(data)
        except Exception:
            pass
    else:
        # Aucun comparable retenu — JSON minimal pour ne pas bloquer la phase 2
        resultat_multiples = json.dumps({
            "comparables_proposes": [],
            "multiples_medians":    {"EV/EBITDA": 0, "P/E": 0, "EV/CA": 0},
            "valeur_multiples":     0,
            "valeur_ev_ebitda":     0,
            "valeur_p_e":           0,
            "valeur_ev_ca":         0,
            "note": "Aucun comparable retenu par l'utilisateur — méthode des multiples non applicable."
        })

    (tache_critique, tache_agregation,
     tache_synthese, crew) = lancer_phase2(
        resultat_dcf              = st.session_state.get("resultat_dcf", "{}"),
        resultat_multiples_valide = resultat_multiples,
        dette_nette               = st.session_state.get("dette_nette", 0),
        nombre_actions            = st.session_state.get("nombre_actions", 1),
        poids_dcf                 = poids_dcf
    )

    def apres_critique(output):
        st.session_state.etapes["critique"] = True
        try:
            data = json.loads(str(output))
            st.session_state.critique_statut     = data.get("statut")
            st.session_state.critique_iterations = data.get("iteration", 1)
        except Exception:
            st.session_state.critique_statut = "VALIDE"

    def apres_agregation(output):
        st.session_state.etapes["agregateur"] = True
        st.session_state.resultats_json = charger_resultats_json()

    def apres_synthese(output):
        st.session_state.etapes["synthese"] = True
        st.session_state.rapport_pret    = True
        st.session_state.phase2_terminee = True  # ✅ ici et pas ailleurs

    tache_critique.callback   = apres_critique
    tache_agregation.callback = apres_agregation
    tache_synthese.callback   = apres_synthese

    crew.kickoff()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Évaluation Entreprise")

    # ── Option 1 : Template officiel ──────────────────────────────────────
    st.markdown("#### 📋 Option 1 — Template officiel")
    st.caption("Téléchargez, remplissez, puis importez.")

    from tools.template_excel import generer_template
    _template_path = generer_template(
        os.path.join(tempfile.gettempdir(), "template_evaluation.xlsx")
    )
    with open(_template_path, "rb") as _f:
        st.download_button(
            label="⬇ Télécharger le template Excel",
            data=_f,
            file_name="template_evaluation.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_template"
        )

    fichier_template = st.file_uploader(
        "Importer le template rempli",
        type=["xlsx", "xls"],
        key="upload_template",
        help="Uniquement le template officiel téléchargé ci-dessus."
    )
    if fichier_template:
        st.success(f"✅ {fichier_template.name}")
        st.caption(f"Taille : {fichier_template.size/1024:.1f} Ko")

    st.markdown("---")

    # ── Option 2 : Document libre ─────────────────────────────────────────
    st.markdown("#### 📄 Option 2 — Document libre")
    st.caption("PDF, Excel ou TXT contenant des données financières.")

    fichier_libre = st.file_uploader(
        "Importer un document financier",
        type=["pdf", "xlsx", "xls", "txt"],
        key="upload_libre",
        help="Rapport annuel, états financiers, bilan CPC..."
    )
    if fichier_libre:
        st.success(f"✅ {fichier_libre.name}")
        st.caption(f"Taille : {fichier_libre.size/1024:.1f} Ko")

    st.markdown("---")

    # ── Pondération ───────────────────────────────────────────────────────
    st.markdown("#### ⚖️ Pondération des méthodes")
    poids_dcf = st.slider(
        "Part du DCF (%)", min_value=10, max_value=90,
        value=int(st.session_state.poids_dcf * 100), step=5
    ) / 100
    st.caption(f"DCF : {poids_dcf:.0%}  —  Multiples : {1-poids_dcf:.0%}")
    st.session_state.poids_dcf = poids_dcf

    st.markdown("---")

    # ── Bouton lancer ─────────────────────────────────────────────────────
    fichier_actif = fichier_template or fichier_libre
    mode = "template" if fichier_template else ("libre" if fichier_libre else None)

    st.text("2. Lancer l'analyse")
    lancer = st.button(
        "▶ Démarrer l'évaluation",
        disabled=(fichier_actif is None)
    )

    st.markdown("---")

    # ── Progression ───────────────────────────────────────────────────────
    st.text("3. Progression")
    etapes_labels = {
        "collecteur":  "🔍 Collecteur",
        "analyste":    "📐 Analyste DCF",
        "comparables": "🔗 Comparables",
        "critique":    "🔎 Critique",
        "agregateur":  "🧮 Agrégateur",
        "synthese":    "📝 Synthèse",
    }
    for cle, label in etapes_labels.items():
        if st.session_state.etapes.get(cle):
            st.success(label)
        else:
            st.markdown(f"⬜ {label}")

    # Statut critique
    if st.session_state.critique_statut:
        statut = st.session_state.critique_statut
        it     = st.session_state.critique_iterations
        if statut == "VALIDE":
            st.success(f"✅ Audit validé ({it} itération(s))")
        elif statut == "FORCE_VALIDATION":
            st.warning(f"⚠️ Validation forcée après {it} itérations")
        else:
            st.error(f"🔴 Audit bloqué — itération {it}/3")

    st.markdown("---")

    # ── Téléchargement rapport ────────────────────────────────────────────
    if st.session_state.rapport_pret:
        rapport_path = "outputs/rapport_valorisation.txt"
        if os.path.exists(rapport_path):
            with open(rapport_path, "r", encoding="utf-8") as f:
                contenu = f.read()
            st.download_button(
                label="⬇ Télécharger le rapport",
                data=contenu,
                file_name="rapport_valorisation.txt",
                mime="text/plain",
                key="dl_rapport"
            )


# ── MAIN ──────────────────────────────────────────────────────────────────────
st.title("Valorisation d'Entreprise — DCF & Multiples")
st.caption("Système multi-agents IA — CrewAI + GPT-4.1-nano  |  6 agents spécialisés")
st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# CAS 1 — Aucun fichier chargé
# ════════════════════════════════════════════════════════════════════════════
if not fichier_actif:
    st.info("👈 Déposez un document financier dans la barre latérale pour commencer.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### 📄 Formats acceptés")
        st.write("PDF, Excel (.xlsx / .xls), Texte (.txt)")
        st.write("Ou utilisez le **template officiel** pour une analyse optimale.")
    with col2:
        st.markdown("#### 🤖 6 Agents IA")
        st.write("Collecteur → DCF → Comparables → Critique → Agrégateur → Synthèse")
    with col3:
        st.markdown("#### 📊 Résultats")
        st.write("Valeur DCF, Multiples, fourchette, valeur/action, rapport complet")

# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# CAS 2 — Lancement Phase 1
# ════════════════════════════════════════════════════════════════════════════
elif lancer:
    suffix = os.path.splitext(fichier_actif.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(fichier_actif.read())
        chemin_tmp = tmp.name

    # Reset complet
    st.session_state.etapes              = {k: False for k in st.session_state.etapes}
    st.session_state.rapport_pret        = False
    st.session_state.resultats_json      = None
    st.session_state.comparables_json    = None
    st.session_state.comparables_valides = None
    st.session_state.critique_statut     = None
    st.session_state.critique_iterations = 0
    st.session_state.phase1_terminee     = False
    st.session_state.phase2_terminee     = False

    with st.spinner("🤖 Phase 1 — Collecte, DCF et Comparables en cours…"):
        try:
            if mode == "template":
                from tools.extraction_texte import ExtractionTexte, TemplateNonConforme
                try:
                    ExtractionTexte.read_template(chemin_tmp)
                except TemplateNonConforme as e:
                    st.error(f"❌ Template non conforme : {e}")
                    os.unlink(chemin_tmp)
                    st.stop()
            else:
                from tools.extraction_texte import ExtractionTexte, DocumentNonExploitable
                try:
                    ExtractionTexte.read(chemin_tmp)
                except DocumentNonExploitable as e:
                    st.error(f"❌ Document rejeté : {e}")
                    os.unlink(chemin_tmp)
                    st.stop()

            lancer_phase1_ui(chemin_tmp, mode=mode)

        except Exception as e:
            st.error(f"❌ Erreur Phase 1 : {e}")
        finally:
            if os.path.exists(chemin_tmp):
                try:
                    time.sleep(0.3)
                    os.unlink(chemin_tmp)
                except PermissionError:
                    pass

    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# CAS 2b — Validation des comparables par l'utilisateur
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.get("phase1_terminee") and not st.session_state.get("phase2_terminee"):

    st.subheader("🔗 Validation des comparables boursiers")
    st.info(
        "L'agent a proposé les comparables ci-dessous. "
        "Cochez ceux que vous souhaitez **conserver** pour le calcul des multiples, "
        "puis cliquez sur **Valider et continuer**."
    )

    comparables = st.session_state.get("comparables_json", [])

    if not comparables:
        st.warning("Aucun comparable détecté — l'agent continuera sans multiples boursiers.")
        comparables_retenus = []
    else:
        comparables_retenus = []
        for i, comp in enumerate(comparables):
            aberrant = comp.get("aberrant", False)
            tag = " ⚠️ *multiple aberrant*" if aberrant else ""
            nom = comp.get("nom") or comp.get("name") or f"Comparable {i + 1}"

            col_check, col_info = st.columns([1, 6])
            with col_check:
                retenu = st.checkbox(
                    "", value=not aberrant,
                    key=f"comp_{i}",
                )
            with col_info:
                st.markdown(
                    f"**{nom}**{tag} — "
                    f"EV/EBITDA : **{comp.get('ev_ebitda', 'N/A')}x** | "
                    f"P/E : **{comp.get('pe', 'N/A')}x**"  # ← EV/CA supprimé
                )
            if retenu:
                comparables_retenus.append(comp)

    st.markdown("---")
    col_info, col_btn = st.columns([3, 1])
    with col_info:
        nb_retenus = len(comparables_retenus) if comparables_retenus else 0
        nb_total = len(comparables) if comparables else 0
        st.caption(f"**{nb_retenus}** comparable(s) retenu(s) sur {nb_total}")
    with col_btn:
        valider = st.button("✅ Valider et continuer", type="primary")

    if valider:
        st.session_state.comparables_valides = comparables_retenus

        with st.spinner("🤖 Phase 2 — Audit, Agrégation et Synthèse en cours…"):
            try:
                lancer_phase2_ui(poids_dcf=st.session_state.poids_dcf)
            except Exception as e:
                st.error(f"❌ Erreur Phase 2 : {e}")
                st.stop()

        # Ne pas mettre phase2_terminee ici — le callback apres_synthese s'en charge
        st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# CAS 3 — Résultats disponibles
# ════════════════════════════════════════════════════════════════════════════
elif st.session_state.rapport_pret:

    # ── Chargement des données ────────────────────────────────────────────
    res = st.session_state.resultats_json or charger_resultats_json()
    methode_label = res.get("composition", {}).get("methode", "DCF + Multiples") if res else "N/A"

    # Fallback : parser le rapport texte si le JSON n'est pas disponible
    rapport_texte = ""
    rapport_path  = "outputs/rapport_valorisation.txt"
    if os.path.exists(rapport_path):
        with open(rapport_path, "r", encoding="utf-8") as f:
            rapport_texte = f.read()

    if res:
        ve_dict   = res.get("valeur_entreprise", {})
        eq_dict   = res.get("valeur_capitaux_propres", {})
        vpa_dict  = res.get("valeur_par_action", {})
        compo     = res.get("composition", {})
        fcf_list  = res.get("fcf_forecast", [])
        pct_term  = res.get("pct_terminal", 0)
        wacc_val  = res.get("wacc")

        ve_cent   = ve_dict.get("centrale")
        ve_pess   = ve_dict.get("pessimiste")
        ve_opti   = ve_dict.get("optimiste")
        ve_dcf    = compo.get("ve_dcf")
        ve_mult   = compo.get("ve_multiples")
        dette     = compo.get("dette_nette", 0)
        pv_fcf    = ve_dcf  * (1 - pct_term) if ve_dcf and pct_term else ve_cent * 0.40 if ve_cent else 0
        pv_term   = ve_dcf  * pct_term        if ve_dcf and pct_term else ve_cent * 0.60 if ve_cent else 0
    else:
        # Fallback texte
        parsed    = parser_resultats(rapport_texte)
        ve_cent   = parsed["valeur_entreprise"]
        ve_pess   = parsed["pessimiste"]  or (ve_cent * 0.85 if ve_cent else None)
        ve_opti   = parsed["optimiste"]   or (ve_cent * 1.15 if ve_cent else None)
        ve_dcf    = ve_mult = wacc_val = None
        dette     = 0
        fcf_list  = [ve_cent * 0.07 * (1.04**i) for i in range(5)] if ve_cent else []
        pv_fcf    = ve_cent * 0.40 if ve_cent else 0
        pv_term   = ve_cent * 0.60 if ve_cent else 0
        vpa_dict  = {}

    # ── KPIs ─────────────────────────────────────────────────────────────
    st.subheader("📌 Indicateurs clés")
    k1, k2, k3, k4 = st.columns(4)

    kpis = [
        (k1, "Valeur centrale", formater_mad(ve_cent)),
        (k2, "Scénario pessimiste", formater_mad(ve_pess)),
        (k3, "Scénario optimiste", formater_mad(ve_opti)),
        (k4, "WACC", f"{wacc_val:.1%}" if wacc_val else "N/A"),

    ]
    st.caption(f"📐 Méthode : **{methode_label}**")

    for col, label, val in kpis:
        with col:
            st.markdown(f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Statut audit critique ─────────────────────────────────────────────
    statut = st.session_state.critique_statut
    if statut == "VALIDE":
        st.markdown(f'<div class="critique-ok">✅ Audit qualité : <b>VALIDÉ</b> '
                    f'({st.session_state.critique_iterations} itération(s))</div>',
                    unsafe_allow_html=True)
    elif statut == "FORCE_VALIDATION":
        st.markdown(f'<div class="critique-warn">⚠️ Validation forcée après '
                    f'{st.session_state.critique_iterations} itérations — '
                    f'consulter le rapport pour les réserves.</div>',
                    unsafe_allow_html=True)
    elif statut:
        st.markdown(f'<div class="critique-block">🔴 Audit : <b>{statut}</b></div>',
                    unsafe_allow_html=True)

    st.markdown("---")

    # ── Graphiques ────────────────────────────────────────────────────────
    st.subheader("📊 Analyses graphiques")

    col1, col2 = st.columns(2)
    with col1:
        if fcf_list:
            st.plotly_chart(graphique_fcf(fcf_list), use_container_width=True)
    with col2:
        if pv_fcf and pv_term:
            st.plotly_chart(graphique_decomposition(pv_fcf, pv_term),
                            use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        if all([ve_pess, ve_cent, ve_opti]):
            st.plotly_chart(graphique_scenarios(ve_pess, ve_cent, ve_opti),
                            use_container_width=True)
    with col4:
        if pv_fcf and pv_term:
            st.plotly_chart(graphique_waterfall(pv_fcf, pv_term, dette),
                            use_container_width=True)

    # Graphique DCF vs Multiples (si données dispo)
    if ve_dcf and ve_mult and ve_cent:
        st.plotly_chart(
            graphique_comparaison_methodes(ve_dcf, ve_mult, ve_cent),
            use_container_width=True
        )

    # ── Comparables ───────────────────────────────────────────────────────
    if st.session_state.comparables_json:
        st.markdown("---")
        st.subheader("🔗 Comparables boursiers retenus")
        try:
            df_comp = st.dataframe(
                st.session_state.comparables_json,
                use_container_width=True
            )
        except Exception:
            st.json(st.session_state.comparables_json)

    st.markdown("---")

    # ── Rapport complet ───────────────────────────────────────────────────
    if rapport_texte:
        with st.expander("📄 Voir le rapport complet"):
            st.text(rapport_texte)

# ════════════════════════════════════════════════════════════════════════════
# CAS 4 — Fichier chargé mais analyse non lancée
# ════════════════════════════════════════════════════════════════════════════
else:
    st.warning("⏳ Fichier chargé. Configurez la pondération puis cliquez sur **Démarrer l'évaluation**.")
    if mode == "template":
        st.info("📋 Mode **Template officiel** détecté — analyse optimale.")
    else:
        st.info("📄 Mode **Document libre** détecté — l'agent validera le contenu avant analyse.")