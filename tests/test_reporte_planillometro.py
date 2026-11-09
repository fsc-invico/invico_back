"""Tests de la homogeneización del acumulado histórico del Planillómetro.

Regresión del doble conteo por estructuras duplicadas (variantes 421/422 de
una misma actividad con distinta descripción en rf610).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_reporte_planillometro -v
"""

import unittest

import pandas as pd

from src.analysis.services.reporte_planillometro import _homogenize_acum_2008

DESC_421 = "53 - CONST200 VIVOCE"
DESC_422 = "53 - CONST.200 VIV.O.C.E.INFR.C/PROVISION"
PATRICIA_421 = '53 - Const.  200 Viv.- O.C. E  Infraest. c/Prov.Terreno-Gpo "C"'
PATRICIA_422 = '53 - Const.  200 Viv.- O.C. E  Infraest. c/Prov.Terreno-Gpo "D"'
GROUP_COLS = [
    "desc_programa",
    "desc_proyecto",
    "desc_actividad",
    "actividad",
    "partida",
]


# -------------------------------------------------
def build_icaro_df() -> pd.DataFrame:
    """icaro: mismo actividad, dos partidas con desc_actividad distinta."""
    base = {
        "desc_programa": "19 - PROGRAMA FEDERAL PLURIANUAL DE",
        "desc_subprograma": "00 - SIN SUBPROGRAMA",
        "desc_proyecto": "02 - CAPITAL",
        "actividad": "19-00-02-53",
    }
    return pd.DataFrame(
        [
            {
                **base,
                "ejercicio": 2010,
                "partida": "421",
                "desc_obra": "Obra 421",
                "importe": 100.0,
                "avance": 1,
                "desc_actividad": DESC_421,
            },
            {
                **base,
                "ejercicio": 2011,
                "partida": "422",
                "desc_obra": "Obra 422",
                "importe": 200.0,
                "avance": 1,
                "desc_actividad": DESC_422,
            },
        ]
    )


# -------------------------------------------------
def build_hist_df() -> pd.DataFrame:
    """Histórico de Patricia con sus propias descripciones (similares pero no iguales)."""
    return pd.DataFrame(
        [
            {
                "estructura": "19-00-02-53-421",
                "actividad": "19-00-02-53",
                "partida": "421",
                "desc_programa": "19 - PROG. FED. PLURIANUAL DE CONSTR. DE VIVIENDAS",
                "desc_subprograma": None,
                "desc_proyecto": "02 - CAPITAL",
                "desc_actividad": PATRICIA_421,
                "acum_2008": 13_579_436.34,
                "alta": "2006",
            },
            {
                "estructura": "19-00-02-53-422",
                "actividad": "19-00-02-53",
                "partida": "422",
                "desc_programa": "19 - PROG. FED. PLURIANUAL DE CONSTR. DE VIVIENDAS",
                "desc_subprograma": None,
                "desc_proyecto": "02 - CAPITAL",
                "desc_actividad": PATRICIA_422,
                "acum_2008": 1_049_009.66,
                "alta": "2007",
            },
        ]
    )


# -------------------------------------------------
class TestHomogenizeAcum2008(unittest.TestCase):
    """Valida la homogeneización por estructura completa (actividad + '-' + partida)."""

    # -------------------------------------------------
    def test_hist_recibe_descs_de_su_propia_estructura(self) -> None:
        """Cada fila hist toma la desc icaro de SU estructura (bug: la clave parcial
        (programa, proyecto, actividad) compartía 421 y 422 y daba la vecina)."""
        _, hist = _homogenize_acum_2008(build_icaro_df(), build_hist_df())

        desc_421 = hist.loc[
            hist["estructura"] == "19-00-02-53-421", "desc_actividad"
        ].iloc[0]
        desc_422 = hist.loc[
            hist["estructura"] == "19-00-02-53-422", "desc_actividad"
        ].iloc[0]

        self.assertEqual(desc_421, DESC_421)
        self.assertEqual(desc_422, DESC_422)
        self.assertNotEqual(desc_421, desc_422)

    # -------------------------------------------------
    def test_hist_desc_obra_usa_desc_homogeneizada(self) -> None:
        """desc_obra del histórico se asigna DESPUÉS de homogeneizar."""
        _, hist = _homogenize_acum_2008(build_icaro_df(), build_hist_df())

        for estructura, esperado in [
            ("19-00-02-53-421", DESC_421),
            ("19-00-02-53-422", DESC_422),
        ]:
            fila = hist.loc[hist["estructura"] == estructura].iloc[0]
            self.assertEqual(fila["desc_obra"], esperado)
            self.assertEqual(fila["ejercicio"], 2008)
            self.assertEqual(fila["avance"], 1)

    # -------------------------------------------------
    def test_estructura_reconstruida_cuando_falta(self) -> None:
        """Si el hist viene sin 'estructura', se reconstruye desde actividad + partida."""
        hist = build_hist_df()
        hist.loc[hist["estructura"] == "19-00-02-53-422", "estructura"] = None

        _, hist_out = _homogenize_acum_2008(build_icaro_df(), hist)

        fila = hist_out.loc[hist_out["partida"] == "422"].iloc[0]
        self.assertEqual(fila["estructura"], "19-00-02-53-422")
        self.assertEqual(fila["desc_actividad"], DESC_422)

    # -------------------------------------------------
    def test_estructura_solo_en_hist_conerva_descs(self) -> None:
        """Estructuras sin datos en icaro conservan sus propias descripciones y avisan."""
        hist = build_hist_df()
        hist.loc[len(hist)] = {
            "estructura": "19-00-02-99-421",
            "actividad": "19-00-02-99",
            "partida": "421",
            "desc_programa": "19 - PROG. PATRICIA",
            "desc_subprograma": None,
            "desc_proyecto": "02 - CAPITAL",
            "desc_actividad": "99 - PATRICIA",
            "acum_2008": 50.0,
            "alta": "2006",
        }

        with self.assertLogs("uvicorn", level="WARNING") as captura:
            _, hist_out = _homogenize_acum_2008(build_icaro_df(), hist)

        fila = hist_out.loc[hist_out["estructura"] == "19-00-02-99-421"].iloc[0]
        self.assertEqual(fila["desc_actividad"], "99 - PATRICIA")
        self.assertTrue(
            any("sin datos en icaro" in mensaje for mensaje in captura.output)
        )

    # -------------------------------------------------
    def test_icaro_auto_normaliza_descs_conflictivas(self) -> None:
        """Filas de icaro con la misma estructura pero distinta desc (include_pa6)
        quedan normalizadas a la primera descripción encontrada."""
        df = build_icaro_df().iloc[[0]].copy()
        df_conflicto = df.copy()
        df_conflicto["ejercicio"] = 2012
        df_conflicto["desc_actividad"] = "53 - OTRA DESC SNAPSHOTT"
        df = pd.concat([df, df_conflicto], ignore_index=True)

        with self.assertLogs("uvicorn", level="WARNING") as captura:
            df_out, _ = _homogenize_acum_2008(df, build_hist_df())

        self.assertEqual(df_out["desc_actividad"].nunique(), 1)
        self.assertEqual(df_out["desc_actividad"].iloc[0], DESC_421)
        self.assertTrue(any("en conflicto" in mensaje for mensaje in captura.output))

    # -------------------------------------------------
    def test_salida_sin_estructuras_duplicadas(self) -> None:
        """Regresión end-to-end: las variantes 421/422 no deben duplicar filas."""
        df, hist = _homogenize_acum_2008(build_icaro_df(), build_hist_df())
        df = df.loc[df["ejercicio"].astype(int) > 2008]
        combo = pd.concat([df, hist], ignore_index=True)

        final = (
            combo.groupby(GROUP_COLS, dropna=True)
            .agg(acum=("importe", "sum"))
            .reset_index()
        )
        final["estructura"] = final["actividad"] + "-" + final["partida"]

        self.assertTrue(final["estructura"].is_unique)
        self.assertEqual(
            sorted(final["estructura"].tolist()),
            ["19-00-02-53-421", "19-00-02-53-422"],
        )

        # Los importes se conservan: hist + icaro por estructura, sin duplicar
        totales = final.set_index("estructura")["acum"]
        self.assertAlmostEqual(totales["19-00-02-53-421"], 13_579_436.34 + 100.0)
        self.assertAlmostEqual(totales["19-00-02-53-422"], 1_049_009.66 + 200.0)


if __name__ == "__main__":
    unittest.main()