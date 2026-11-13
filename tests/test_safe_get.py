"""Tests de las utilidades de sanitización de DataFrames (src/utils/safe_get.py).

Cubren la regresión de pandas 3.x: ``DataFrame.apply`` / ``DataFrame.map``
re-infiere los dtypes de las columnas ``object`` (a ``float64`` o
``StringDtype(na_value=nan)``) y revertía ``None`` a ``NaN``, lo que
abortaba la subida a Google Sheets con:

    Out of range float values are not JSON compliant: nan

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_safe_get -v
"""

import json
import unittest
from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from src.utils import (
    sanitize_dataframe_for_json,
    sanitize_dataframe_for_json_with_datetime,
)


# -------------------------------------------------
def df_con_nulos() -> pd.DataFrame:
    """DataFrame tipo ``siif_gastos``: un nulo por cada dtype problemático."""
    return pd.DataFrame(
        {
            "ejercicio": [2025, 2025],
            "partida": pd.Series(["372", None]),  # str dtype (na_value=nan)
            "importe": [100.5, np.nan],  # float64 con NaN
            "glosa": pd.Series(["Rendicion", np.nan], dtype=object),  # object con np.nan
            "fecha": pd.to_datetime(["2025-01-15", None]),  # datetime64 con NaT
        }
    )


# -------------------------------------------------
class TestSanitizeDataFrames(unittest.TestCase):
    """Ambos sanitizadores producen DataFrames sin nan/inf (JSON compliant)."""

    # -------------------------------------------------
    def test_with_datetime_es_json_compliant(self) -> None:
        """La subida a Google Sheets serializa con allow_nan=False."""
        limpia = sanitize_dataframe_for_json_with_datetime(df_con_nulos())

        filas = limpia.values.tolist()  # mismos valores que sube gspread
        registros = limpia.to_dict(orient="records")
        json.dumps(filas, allow_nan=False)
        json.dumps(registros, allow_nan=False)

    # -------------------------------------------------
    def test_sin_datetime_es_json_compliant(self) -> None:
        """La variante sin formato de fecha también queda sin nan."""
        df = df_con_nulos().drop(columns=["fecha"])

        limpia = sanitize_dataframe_for_json(df)

        json.dumps(limpia.values.tolist(), allow_nan=False)
        json.dumps(limpia.to_dict(orient="records"), allow_nan=False)

    # -------------------------------------------------
    def test_nulos_quedan_como_none(self) -> None:
        """Cada nan/NaT termina como None (JSON null) en todos los dtypes."""
        limpia = sanitize_dataframe_for_json_with_datetime(df_con_nulos())

        segunda_fila = limpia.to_dict(orient="records")[1]

        self.assertIsNone(segunda_fila["partida"])
        self.assertIsNone(segunda_fila["importe"])
        self.assertIsNone(segunda_fila["glosa"])
        self.assertIsNone(segunda_fila["fecha"])


    # -------------------------------------------------
    def test_convierte_escalares_numpy_a_nativos(self) -> None:
        """np.int64/np.bool_/np.float64 no son serializables por json."""
        df = pd.DataFrame(
            {
                "entero": [np.int64(5)],
                "booleano": [np.bool_(True)],
                "decimal": [np.float64(2.5)],
            }
        )

        registro = sanitize_dataframe_for_json(df).to_dict(orient="records")[0]

        self.assertIsInstance(registro["entero"], int)
        self.assertIsInstance(registro["booleano"], bool)
        self.assertIsInstance(registro["decimal"], float)

    # -------------------------------------------------
    def test_inf_y_decimal_no_finito_quedan_none(self) -> None:
        """±inf y Decimal('NaN') también rompen json.dumps(allow_nan=False)."""
        df = pd.DataFrame(
            {
                "x": [float("inf"), float("-inf")],
                "d": [Decimal("1.5"), Decimal("NaN")],
            }
        )

        registros = sanitize_dataframe_for_json(df).to_dict(orient="records")

        json.dumps(registros, allow_nan=False)
        self.assertIsNone(registros[0]["x"])
        self.assertIsNone(registros[1]["x"])
        self.assertEqual(registros[0]["d"], 1.5)
        self.assertIsNone(registros[1]["d"])

    # -------------------------------------------------
    def test_formatea_fechas_como_dd_mm_aaaa(self) -> None:
        """Mantiene el formato historico dd/mm/aaaa de la variante con datetime."""
        df = pd.DataFrame({"fecha": [datetime(2025, 2, 1)]})

        limpia = sanitize_dataframe_for_json_with_datetime(df)

        self.assertEqual(limpia["fecha"].iloc[0], "01/02/2025")

    # -------------------------------------------------
    def test_convierte_id_a_string(self) -> None:
        """Los id internos viajan como string (ObjectId de Mongo)."""
        df = pd.DataFrame({"id": [123], "importe": [np.nan]})

        limpia = sanitize_dataframe_for_json_with_datetime(df)

        self.assertEqual(limpia["id"].iloc[0], "123")

    # -------------------------------------------------
    def test_es_idempotente(self) -> None:
        """Sanitizar dos veces (servicio + upload) no cambia el resultado."""
        una_vez = sanitize_dataframe_for_json_with_datetime(df_con_nulos())
        dos_veces = sanitize_dataframe_for_json_with_datetime(una_vez)

        json.dumps(dos_veces.values.tolist(), allow_nan=False)
        self.assertEqual(una_vez.to_dict("records"), dos_veces.to_dict("records"))

    # -------------------------------------------------
    def test_dataframes_vacios_se_devuelven_tal_cual(self) -> None:
        """Los DataFrames vacíos se devuelven sin columnas inventadas."""
        vacio = pd.DataFrame()
        sin_filas = pd.DataFrame(columns=["importe", "glosa"])

        self.assertTrue(sanitize_dataframe_for_json(vacio).empty)
        self.assertTrue(sanitize_dataframe_for_json_with_datetime(vacio).empty)
        self.assertEqual(
            list(sanitize_dataframe_for_json(sin_filas).columns),
            ["importe", "glosa"],
        )


# -------------------------------------------------
if __name__ == "__main__":
    unittest.main()
