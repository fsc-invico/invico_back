"""Tests del export solo-Google-Sheets de Control Aporte Empresario.

- ``export`` responde JSON de inmediato y encola la tarea de fondo
  (sin generar el archivo Excel).
- ``_export_to_google_sheets`` sube las 5 hojas del módulo en
  background hacia la spreadsheet key del módulo.
- ``_build_df_and_upload`` sanitiza NaN y descarta los id internos.
- Superficie de rutas: snapshot CRUD + ``/generate*`` + ``/export``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_aporte_empresario -v
"""

import asyncio
import json
import unittest
from typing import Any, List
from unittest import mock

import pandas as pd

from src.analysis.routes.control_aporte_empresario import (
    control_aporte_empresario_router,
)
from src.analysis.schemas import ControlAporteEmpresarioLiteFilter
from src.analysis.services import ControlAporteEmpresarioService
from src.analysis.services.control_aporte_empresario import (
    SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO,
)

HOJAS_ESPERADAS: list[str] = [
    "recursos_siif_db",
    "retenciones_siif_db",
    "retenciones_icaro_db",
    "control_cruzado_siif_db",
    "control_cruzado_icaro_db",
]


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
def construir_servicio(
    repository: RepositorioFalso,
) -> ControlAporteEmpresarioService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlAporteEmpresarioService(
        repository=repository,
        recursos_service=None,
        retenciones_service=None,
        icaro_service=None,
        cta_cte_service=None,
    )


# -------------------------------------------------
class TestExportControlAporteEmpresario(unittest.IsolatedAsyncioTestCase):
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
                params=ControlAporteEmpresarioLiteFilter(ejercicio=2024),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO
        )
        for hoja in HOJAS_ESPERADAS:
            self.assertIn(hoja, respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_sube_cinco_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube las 5 hojas a GS sin construir XLS."""
        import src.analysis.services.control_aporte_empresario as service_module

        # El módulo ya ni siquiera importa la respuesta binaria
        self.assertFalse(hasattr(service_module, "StreamingResponse"))

        servicio = construir_servicio(RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_aporte_empresario."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_recursos",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_retenciones_from_siif",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_retenciones_from_icaro",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "generate_icaro",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "generate_siif",
            new=mock.AsyncMock(return_value=[]),
        ):
            await servicio._export_to_google_sheets(
                params=ControlAporteEmpresarioLiteFilter(ejercicio=2024)
            )

        # Las 5 hojas subidas a Google Sheets, en el orden esperado
        self.assertEqual(upload_mock.call_count, len(HOJAS_ESPERADAS))
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(hojas, HOJAS_ESPERADAS)
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"],
                SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO,
            )

    # -------------------------------------------------
    def test_sube_hoja_sin_celdas_nan(self) -> None:
        """_build_df_and_upload sanitiza antes de subir (defensa).

        gspread serializa con ``json.dumps(allow_nan=False)``: una sola
        celda NaN aborta la subida completa y deja la hoja vacía.
        """
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "cta_cte": ["130101-01", "334", None],
                "recurso": [100.5, float("nan"), 3.0],
                "retencion": [90.0, None, float("inf")],
            }
        )

        with mock.patch(
            "src.analysis.services.control_aporte_empresario."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            ControlAporteEmpresarioService._build_df_and_upload(
                df, "control_cruzado_siif_db"
            )

        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_cruzado_siif_db")
        # Los id internos no viajan a la hoja
        self.assertNotIn("id", df_subido.columns)
        # Misma validación que hace gspread/requests al serializar
        json.dumps(df_subido.values.tolist(), allow_nan=False)
        self.assertIsNone(df_subido["cta_cte"].tolist()[2])
        self.assertIsNone(df_subido["recurso"].tolist()[1])
        self.assertIsNone(df_subido["retencion"].tolist()[2])


# -------------------------------------------------
class TestRutasControlAporteEmpresario(unittest.TestCase):
    """La superficie de rutas expone snapshot CRUD + generate* + export."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_aporte_empresario_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlAporteEmpresario", "GET"),  # Get All (snapshot)
            ("/controlAporteEmpresario", "POST"),  # Add Many
            ("/controlAporteEmpresario", "DELETE"),  # Delete Many
            ("/controlAporteEmpresario/generateSIIF", "GET"),  # Cruce SIIF
            ("/controlAporteEmpresario/generateIcaro", "GET"),  # Cruce ICARO
            ("/controlAporteEmpresario/export", "GET"),  # Solo Google Sheets
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()
