"""Tests del export solo-Google-Sheets de Control Icaro.

- ``export`` responde JSON de inmediato y encola la tarea de fondo
  (sin generar el archivo Excel) y rechaza requests sin ``ejercicio``.
- ``_export_to_google_sheets`` sube las 7 hojas de los 3 subreportes
  en background hacia la spreadsheet key del módulo.
- ``_build_df_and_upload`` sanitiza NaN y descarta los id internos.
- Superficie de rutas: crudos/compute + ``/export``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_icaro -v
"""

import asyncio
import json
import unittest
from unittest import mock

import pandas as pd
from fastapi import HTTPException

from src.analysis.routes.control_icaro import control_icaro_router
from src.analysis.schemas import ControlIcaroLiteFilter
from src.analysis.services import ControlIcaroService
from src.analysis.services.control_icaro import SPREADSHEET_KEY_CONTROL_ICARO

HOJAS_ESPERADAS: list[str] = [
    "control_ejecucion_anual_db",
    "control_comprobantes_db",
    "control_pa6_db",
    "siif_comprobantes_db",
    "siif_obras_db",
    "siif_pa6_db",
    "icaro_comprobantes_db",
]


# -------------------------------------------------
def construir_servicio() -> ControlIcaroService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlIcaroService(
        gastos_service=None,
        icaro_service=None,
        rf602_service=None,
        rfondo07tp_service=None,
    )


# -------------------------------------------------
class TestExportControlIcaro(unittest.IsolatedAsyncioTestCase):
    """El export solo sube a Google Sheets (sin Excel), en background."""

    # -------------------------------------------------
    async def test_export_responde_json_y_lanza_tarea(self) -> None:
        """Responde JSON de inmediato y lanza la tarea de fondo."""
        servicio = construir_servicio()
        with mock.patch.object(
            servicio,
            "_export_to_google_sheets",
            new=mock.AsyncMock(),
        ) as tarea_mock:
            respuesta = await servicio.export(
                params=ControlIcaroLiteFilter(ejercicio="2024"),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_ICARO
        )
        for hoja in HOJAS_ESPERADAS:
            self.assertIn(hoja, respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_requiere_ejercicio(self) -> None:
        """Sin ejercicio se responde 400 (no se encola nada)."""
        servicio = construir_servicio()

        with self.assertRaises(HTTPException) as ctx:
            await servicio.export(params=ControlIcaroLiteFilter())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ejercicio", ctx.exception.detail)

    # -------------------------------------------------
    async def test_export_sube_siete_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube las 7 hojas a GS sin construir XLS."""
        import src.analysis.services.control_icaro as service_module

        # El módulo ya ni siquiera importa la respuesta binaria
        self.assertFalse(hasattr(service_module, "StreamingResponse"))

        servicio = construir_servicio()
        with mock.patch(
            "src.analysis.services.control_icaro."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_siif_gastos",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_siif_obras",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_siif_pa6",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_icaro_comprobantes",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_anual",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_comprobantes",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_pa6",
            new=mock.AsyncMock(return_value=[]),
        ):
            await servicio._export_to_google_sheets(
                params=ControlIcaroLiteFilter(ejercicio="2024")
            )

        # Las 7 hojas subidas a Google Sheets, en el orden esperado
        self.assertEqual(upload_mock.call_count, len(HOJAS_ESPERADAS))
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(hojas, HOJAS_ESPERADAS)
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"],
                SPREADSHEET_KEY_CONTROL_ICARO,
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
                "estructura": ["42100", "42200", None],
                "ejecucion_siif": [100.5, float("nan"), 3.0],
                "ejecucion_icaro": [90.0, None, float("inf")],
            }
        )

        with mock.patch(
            "src.analysis.services.control_icaro."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            ControlIcaroService._build_df_and_upload(
                df, "control_ejecucion_anual_db"
            )

        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_ejecucion_anual_db")
        # Los id internos no viajan a la hoja
        self.assertNotIn("id", df_subido.columns)
        # Misma validación que hace gspread/requests al serializar
        json.dumps(df_subido.values.tolist(), allow_nan=False)
        self.assertIsNone(df_subido["estructura"].tolist()[2])
        self.assertIsNone(df_subido["ejecucion_siif"].tolist()[1])
        self.assertIsNone(df_subido["ejecucion_icaro"].tolist()[2])


# -------------------------------------------------
class TestRutasControlIcaro(unittest.TestCase):
    """La superficie de rutas expone crudos/computes + export."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_icaro_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlIcaro/SIIFGastos", "GET"),  # Crudo SIIF gastos
            ("/controlIcaro/computeControlAnual", "GET"),  # Cruce anual
            ("/controlIcaro/computeControlComprobantes", "GET"),
            ("/controlIcaro/computeControlPA6", "GET"),
            ("/controlIcaro/export", "GET"),  # Solo Google Sheets
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()
