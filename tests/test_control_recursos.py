"""Tests del export solo-Google-Sheets de Control Recursos.

- ``export`` responde JSON de inmediato y encola la tarea de fondo
  (sin generar el archivo Excel) y rechaza requests sin ``ejercicio``.
- ``_export_to_google_sheets`` sube la hoja ``control_recursos`` en
  background hacia la spreadsheet key del módulo.
- ``_build_df_and_upload`` sanitiza NaN y descarta los id internos.
- Superficie de rutas: snapshot CRUD + ``/generate`` + ``/export``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_recursos -v
"""

import asyncio
import json
import unittest
from typing import Any, List
from unittest import mock

import pandas as pd
from fastapi import HTTPException

from src.analysis.routes.control_recursos import control_recursos_router
from src.analysis.schemas import ControlRecursosLiteFilter
from src.analysis.services import ControlRecursosService
from src.analysis.services.control_recursos import (
    SPREADSHEET_KEY_CONTROL_RECURSOS,
)


# -------------------------------------------------
class DocumentoFalso:
    """Documento mínimo con la interfaz ``model_dump`` del repositorio."""

    # -------------------------------------------------
    def __init__(self, datos: dict) -> None:
        self._datos = datos

    # -------------------------------------------------
    def model_dump(self, by_alias: bool = False) -> dict:
        return dict(self._datos)


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que responde el export."""

    # -------------------------------------------------
    def __init__(self, filas: List[Any] = None) -> None:
        self.filas = filas if filas is not None else []

    # -------------------------------------------------
    async def find_with_filter_params(self, params: Any) -> List[Any]:
        return list(self.filas)


# -------------------------------------------------
def construir_servicio(repository: RepositorioFalso) -> ControlRecursosService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlRecursosService(
        repository=repository,
        siif_service=None,
        banco_service=None,
    )


# -------------------------------------------------
def fila_valida(ejercicio: int) -> dict:
    return {
        "ejercicio": ejercicio,
        "mes": "01",
        "cta_cte": "130101-01",
        "grupo": "FONAVI",
        "recursos_siif": 100.0,
        "depositos_banco": 90.0,
    }


# -------------------------------------------------
class TestExportControlRecursos(unittest.IsolatedAsyncioTestCase):
    """El export solo sube a Google Sheets (sin Excel), en background."""

    # -------------------------------------------------
    async def test_export_responde_json_y_lanza_tarea(self) -> None:
        """Responde JSON de inmediato y lanza la tarea de fondo."""
        servicio = construir_servicio(RepositorioFalso())
        with mock.patch.object(
            servicio,
            "_export_to_google_sheets",
            new=mock.AsyncMock(),
        ) as tarea_mock:
            respuesta = await servicio.export(
                params=ControlRecursosLiteFilter(ejercicio="2024"),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_RECURSOS
        )
        self.assertIn("control_recursos", respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_requiere_ejercicio(self) -> None:
        """Sin ejercicio se responde 400 (no se encola nada)."""
        servicio = construir_servicio(RepositorioFalso())

        with self.assertRaises(HTTPException) as ctx:
            await servicio.export(params=ControlRecursosLiteFilter())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ejercicio", ctx.exception.detail)

    # -------------------------------------------------
    async def test_export_sube_hoja_sin_excel(self) -> None:
        """La tarea de fondo sube la hoja sin construir XLS binario."""
        import src.analysis.services.control_recursos as service_module

        # El módulo ya ni siquiera importa la respuesta binaria
        self.assertFalse(hasattr(service_module, "StreamingResponse"))

        servicio = construir_servicio(
            RepositorioFalso([DocumentoFalso(fila_valida(2024))])
        )
        with mock.patch(
            "src.analysis.services.control_recursos."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            await servicio._export_to_google_sheets(
                params=ControlRecursosLiteFilter(ejercicio="2024")
            )

        self.assertEqual(upload_mock.call_count, 1)
        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_recursos")
        self.assertEqual(
            upload_mock.call_args.kwargs["spreadsheet_key"],
            SPREADSHEET_KEY_CONTROL_RECURSOS,
        )
        self.assertNotIn("id", df_subido.columns)

    # -------------------------------------------------
    def test_sube_hoja_sin_celdas_nan(self) -> None:
        """_build_df_and_upload sanitiza antes de subir (defensa).

        gspread serializa con ``json.dumps(allow_nan=False)``: una sola
        celda NaN aborta la subida completa y deja la hoja vacía.
        """
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "grupo": ["FONAVI", "OTROS", None],
                "recursos_siif": [100.5, float("nan"), 3.0],
                "depositos_banco": [90.0, None, float("inf")],
            }
        )

        with mock.patch(
            "src.analysis.services.control_recursos."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            ControlRecursosService._build_df_and_upload(df, "control_recursos")

        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_recursos")
        # Los id internos no viajan a la hoja
        self.assertNotIn("id", df_subido.columns)
        # Misma validación que hace gspread/requests al serializar
        json.dumps(df_subido.values.tolist(), allow_nan=False)
        self.assertIsNone(df_subido["grupo"].tolist()[2])
        self.assertIsNone(df_subido["recursos_siif"].tolist()[1])
        self.assertIsNone(df_subido["depositos_banco"].tolist()[2])


# -------------------------------------------------
class TestRutasControlRecursos(unittest.TestCase):
    """La superficie de rutas expone snapshot CRUD + generate + export."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_recursos_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlRecursos", "GET"),  # Get All (snapshot persistido)
            ("/controlRecursos", "POST"),  # Add Many (congela el snapshot)
            ("/controlRecursos", "DELETE"),  # Delete Many
            ("/controlRecursos/generate", "GET"),  # Cruce on-demand
            ("/controlRecursos/export", "GET"),  # Solo Google Sheets
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()
