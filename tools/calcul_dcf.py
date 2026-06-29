from typing import List

class DCFModel:

    @staticmethod
    def projeter_fcf(
        ebit_historique: List[float],
        da_historique: List[float],
        capex_historique: List[float],
        bfr_historique: List[float],
        taux_is: float,
        taux_croissance: float,
        n_projections: int = 5
    ) -> List[float]:
        """
        Projette les FCF sur n années à partir des moyennes historiques.
        FCF = EBIT*(1-IS) + D&A - CAPEX - ΔBFR
        """
        ebit_moy  = sum(ebit_historique)  / len(ebit_historique)
        da_moy    = sum(da_historique)    / len(da_historique)
        capex_moy = sum(capex_historique) / len(capex_historique)

        # ΔBFR : moyenne des variations
        delta_bfr_moy = sum(bfr_historique) / len(bfr_historique)

        fcf_list = []
        for t in range(1, n_projections + 1):
            facteur   = (1 + taux_croissance) ** t
            ebit_proj = ebit_moy  * facteur
            da_proj   = da_moy    * facteur
            capex_proj= capex_moy * facteur
            nopat     = ebit_proj * (1 - taux_is)
            fcf       = nopat + da_proj - capex_proj - delta_bfr_moy
            fcf_list.append(round(fcf, 2))

        return fcf_list

    @staticmethod
    def enterprise_value(
        fcf_forecast: List[float],
        wacc: float,
        terminal_growth: float
    ) -> dict:
        """
        Calcule la valeur d'entreprise DCF.
        Retourne VE, VA des FCF, VA terminale et leur ratio.
        """
        if wacc <= terminal_growth:
            raise ValueError(
                f"WACC ({wacc:.2%}) doit être strictement supérieur "
                f"au taux de croissance terminal ({terminal_growth:.2%})"
            )

        # VA des FCF
        pv_fcf = sum(
            fcf / ((1 + wacc) ** t)
            for t, fcf in enumerate(fcf_forecast, start=1)
        )

        # Valeur terminale
        terminal_value = (
            fcf_forecast[-1] * (1 + terminal_growth)
            / (wacc - terminal_growth)
        )
        pv_terminal = terminal_value / ((1 + wacc) ** len(fcf_forecast))

        ve = pv_fcf + pv_terminal
        pct_terminal = pv_terminal / ve if ve != 0 else 0

        return {
            "enterprise_value": round(ve, 2),
            "pv_fcf":           round(pv_fcf, 2),
            "pv_terminal":      round(pv_terminal, 2),
            "pct_terminal":     round(pct_terminal, 4),   # ex: 0.87 = 87%
            "terminal_value":   round(terminal_value, 2),
            "wacc":             wacc,
            "terminal_growth":  terminal_growth,
            "fcf_forecast":     fcf_forecast
        }

    @staticmethod
    def calcul_wacc(
        cout_dette: float,
        taux_is: float,
        dette_nette: float,
        capitaux_propres: float,
        beta: float,
        taux_sans_risque: float   = 0.038,   # BDT 10 ans Maroc ~3.8%
        prime_risque_marche: float = 0.065,  # Prime Maroc ~6.5%
    ) -> dict:
        """
        WACC = Ke * E/(D+E) + Kd*(1-IS) * D/(D+E)
        Ke   = Rf + β * (Rm - Rf)   [CAPM]
        """
        total = dette_nette + capitaux_propres
        if total <= 0:
            raise ValueError("Dette nette + Capitaux propres doit être > 0")

        weight_e = capitaux_propres / total
        weight_d = dette_nette      / total

        ke   = taux_sans_risque + beta * prime_risque_marche
        wacc = ke * weight_e + cout_dette * (1 - taux_is) * weight_d

        return {
            "wacc":               round(wacc,   4),
            "ke":                 round(ke,     4),
            "weight_equity":      round(weight_e, 4),
            "weight_debt":        round(weight_d, 4),
            "cout_dette_apres_is": round(cout_dette * (1 - taux_is), 4),
        }