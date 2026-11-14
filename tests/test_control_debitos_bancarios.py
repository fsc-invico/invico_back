"""Tests del patrón generate -> POST de Control Débitos Bancarios.

Cubre la paridad con los demás controles:

- ``generate`` delega el cómputo on-demand con el ``ejercicio``
  recibido (sin persistir).
- ``add_many`` congela el snapshot con borrado idempotente por
  ejercicio (clave ``[ejercicio, mes, cta_cte]``).
- ``compute_control_debitos_bancarios`` arma el cruce (partida 355
  SIIF vs imputación 031 del banco) y soporta lados vacíos.
- ``generate_siif_debitos`` normaliza ``grupo`` a 3 dígitos ("1" ->
  "100") y descarta ``importe_total`` (duplica ``importe``).
- ``export`` solo sube a Google Sheets en background (sin Excel) con
  las hojas ``siif_vs_sscc_db``, ``siif_db`` y ``sscc_db``.
- Superficie de rutas: snapshot CRUD (factory) + ``/generate`` +
  ``/export``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_debitos_bancarios -v
"""

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any, List
from unittest import mock

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from src.analysis.routes.control_debitos_bancarios import (
    control_debitos_bancarios_router,
)
from src.analysis.schemas import (
    ControlDebitosBancariosFilter,
    ControlDebitosBancariosGenerateFilter,
    ControlDebitosBancariosLiteFilter,
    ControlDebitosBancariosReport,
)
from src.analysis.services import ControlDebitosBancariosService
from src.analysis.services.control_debitos_bancarios import (
    SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS,
)


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 4) -> None:
        self.filas_previas = filas_previas
        self.deleted_filters: List[dict] = []
        self.deleted_all_llamado = False
        self.saved: List[Any] = []

    # -------------------------------------------------
    async def count_by_fields(self, filters: dict) -> int:
        return self.filas_previas

    # -------------------------------------------------
    async def delete_by_fields(self, filters: dict) -> int:
        self.deleted_filters.append(filters)
        return self.filas_previas

    # -------------------------------------------------
    async def delete_all(self) -> int:
        self.deleted_all_llamado = True
        return 0

    # -------------------------------------------------
    async def save_all(self, validated: List[Any]) -> SimpleNamespace:
        self.saved.extend(validated)
        return SimpleNamespace(inserted_ids=list(range(len(validated))))


# -------------------------------------------------
def construir_servicio(repository: RepositorioFalso) -> ControlDebitosBancariosService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlDebitosBancariosService(
        control_debitos_bancarios_repo=repository,
        gastos_service=None,
        banco_service=None,
        cta_cte_service=None,
    )


# -------------------------------------------------
def fila_valida(ejercicio: int) -> dict:
    return {
        "ejercicio": ejercicio,
        "mes": "01/2025",
        "cta_cte": "10158-8",
        "ejecutado_siif": 100.0,
        "debitos_sscc": 90.0,
        "diferencia": 10.0,
    }


# -------------------------------------------------
class TestGenerateControlDebitosBancarios(unittest.IsolatedAsyncioTestCase):
    """El endpoint /generate arma el cruce on-demand sin persistir."""

    # -------------------------------------------------
    async def test_generate_delega_en_compute(self) -> None:
        """generate llama a compute_control_debitos_bancarios."""
        servicio = construir_servicio(RepositorioFalso())
        filas_esperadas = [fila_valida(2025)]

        with mock.patch.object(
            servicio,
            "compute_control_debitos_bancarios",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlDebitosBancariosGenerateFilter(ejercicio=2025)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2025)

    # -------------------------------------------------
    async def test_compute_requiere_ejercicio(self) -> None:
        """compute_control_debitos_bancarios avisa si falta el ejercicio."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlDebitosBancariosFilter(ejercicio=None)

        with self.assertRaises(ValueError):
            await servicio.compute_control_debitos_bancarios(params=params)


# -------------------------------------------------
class TestComputeControlDebitosBancarios(unittest.IsolatedAsyncioTestCase):
    """El cruce arma partida 355 (SIIF) vs imputación 031 (banco)."""

    # -------------------------------------------------
    async def test_compute_cruce_happy_path(self) -> None:
        """Verifica diferencia = ejecutado_siif - debitos_sscc."""
        servicio = construir_servicio(RepositorioFalso())
        siif = pd.DataFrame(
            [
                {"ejercicio": 2025, "mes": "01/2025", "cta_cte": "111", "importe": 100.0},
                {"ejercicio": 2025, "mes": "01/2025", "cta_cte": "111", "importe": 50.0},
                {"ejercicio": 2025, "mes": "02/2025", "cta_cte": "222", "importe": 30.0},
            ]
        )
        # sscc viene negativo (débitos) y se invierte en sscc_summarize
        sscc = pd.DataFrame(
            [
                {"ejercicio": 2025, "mes": "01/2025", "cta_cte": "111", "importe": -140.0},
            ]
        )

        with mock.patch.object(
            servicio,
            "generate_siif_debitos",
            new=mock.AsyncMock(return_value=siif),
        ), mock.patch.object(
            servicio,
            "generate_banco_debitos",
            new=mock.AsyncMock(return_value=sscc),
        ):
            filas = await servicio.compute_control_debitos_bancarios(
                params=ControlDebitosBancariosFilter(ejercicio=2025)
            )

        self.assertEqual(len(filas), 2)
        por_mes = {fila["mes"]: fila for fila in filas}
        self.assertEqual(por_mes["01/2025"]["ejecutado_siif"], 150.0)
        self.assertEqual(por_mes["01/2025"]["debitos_sscc"], 140.0)
        self.assertEqual(por_mes["01/2025"]["diferencia"], 10.0)
        # Filas solo en SIIF: sscc en 0 (reindex)
        self.assertEqual(por_mes["02/2025"]["ejecutado_siif"], 30.0)
        self.assertEqual(por_mes["02/2025"]["debitos_sscc"], 0.0)
        self.assertEqual(por_mes["02/2025"]["diferencia"], 30.0)

    # -------------------------------------------------
    async def test_compute_con_lados_vacios_devuelve_vacio(self) -> None:
        """Sin datos de ningún sistema el cruce no truena y devuelve []."""
        servicio = construir_servicio(RepositorioFalso())

        with mock.patch.object(
            servicio,
            "generate_siif_debitos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ), mock.patch.object(
            servicio,
            "generate_banco_debitos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ):
            filas = await servicio.compute_control_debitos_bancarios(
                params=ControlDebitosBancariosFilter(ejercicio=2025)
            )

        self.assertEqual(filas, [])


# -------------------------------------------------
class TestGenerateSiifDebitos(unittest.IsolatedAsyncioTestCase):
    """generate_siif_debitos normaliza 'grupo' y descarta 'importe_total'."""

    # -------------------------------------------------
    async def test_grupo_con_dos_ceros_y_sin_importe_total(self) -> None:
        """El SIIF guarda '1'; la hoja siif_db debe llevar '100' sin duplicar importes."""
        servicio = construir_servicio(RepositorioFalso())
        servicio.gastos_service = SimpleNamespace(
            get_joined_with_rcg01_uejp=mock.AsyncMock(
                return_value=[
                    {
                        "ejercicio": 2025,
                        "partida": "355",
                        "grupo": "1",
                        "importe": 100.0,
                        "importe_total": 100.0,
                    },
                    {
                        "ejercicio": 2025,
                        "partida": "355",
                        "grupo": "4",
                        "importe": 50.0,
                        "importe_total": 50.0,
                    },
                    {
                        "ejercicio": 2025,
                        "partida": "355",
                        "grupo": None,
                        "importe": 10.0,
                        "importe_total": 10.0,
                    },
                ]
            )
        )
        servicio.cta_cte_service = SimpleNamespace(
            cta_cte_unifier=mock.AsyncMock(side_effect=lambda df, nexo: df)
        )

        df = await servicio.generate_siif_debitos(ejercicio=2025)

        # 1 -> 100, 4 -> 400; el nulo no rompe la concatenación
        self.assertEqual(df["grupo"].tolist()[:2], ["100", "400"])
        self.assertTrue(pd.isna(df["grupo"].tolist()[2]))
        # importe_total duplica importe: se descarta de la hoja
        self.assertNotIn("importe_total", df.columns)
        self.assertIn("importe", df.columns)

    # -------------------------------------------------
    async def test_sin_gastos_del_ejercicio_devuelve_vacio(self) -> None:
        """Sin datos crudos la hoja se sube vacía sin truenos."""
        servicio = construir_servicio(RepositorioFalso())
        servicio.gastos_service = SimpleNamespace(
            get_joined_with_rcg01_uejp=mock.AsyncMock(return_value=[])
        )

        df = await servicio.generate_siif_debitos(ejercicio=2025)

        self.assertTrue(df.empty)


# -------------------------------------------------
class TestAddManyControlDebitosBancarios(unittest.IsolatedAsyncioTestCase):
    """POST /controlDebitosBancarios congela el snapshot (por ejercicio)."""

    # -------------------------------------------------
    async def test_add_many_borra_por_ejercicio_y_persiste(self) -> None:
        repository = RepositorioFalso(filas_previas=4)
        servicio = construir_servicio(repository)

        resumen = await servicio.add_many(data=[fila_valida(2025)])

        self.assertEqual(resumen.deleted, 4)
        self.assertEqual(resumen.added, 1)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository.deleted_filters, [{"ejercicio": 2025}])
        self.assertFalse(repository.deleted_all_llamado)
        self.assertIsInstance(repository.saved[0], ControlDebitosBancariosReport)

    # -------------------------------------------------
    async def test_add_many_sin_filas_validas_lanza_400(self) -> None:
        """Si ninguna fila valida, add_many responde 400 y no persiste."""
        repository = RepositorioFalso()
        servicio = construir_servicio(repository)
        invalida = {"ejercicio": 2025, "mes": "01/2025"}  # faltan importes

        with self.assertRaises(HTTPException) as ctx:
            await servicio.add_many(data=[invalida])

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No se encontraron registros válidos", ctx.exception.detail)
        self.assertEqual(len(repository.saved), 0)
        self.assertEqual(repository.deleted_filters, [])


# -------------------------------------------------
class TestExportControlDebitosBancarios(unittest.IsolatedAsyncioTestCase):
    """El export solo sube a Google Sheets (sin Excel), en background."""

    # -------------------------------------------------
    async def test_export_responde_json_y_lanza_tarea(self) -> None:
        """Responde JSON de inmediato y lanza la tarea de fondo (create_task)."""
        servicio = construir_servicio(RepositorioFalso())
        with mock.patch.object(
            servicio,
            "_export_to_google_sheets",
            new=mock.AsyncMock(),
        ) as tarea_mock:
            respuesta = await servicio.export(
                params=ControlDebitosBancariosLiteFilter(ejercicio=2025),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS
        )
        self.assertIn("siif_vs_sscc_db", respuesta["detail"])
        self.assertIn("siif_db", respuesta["detail"])
        self.assertIn("sscc_db", respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_sube_tres_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube exactamente las 3 hojas pedidas."""
        servicio = construir_servicio(RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_debitos_bancarios."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_all",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_debitos_bancarios",
            new=mock.AsyncMock(return_value=[fila_valida(2025)]),
        ), mock.patch.object(
            servicio,
            "generate_siif_debitos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ), mock.patch.object(
            servicio,
            "generate_banco_debitos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ):
            await servicio._export_to_google_sheets(
                params=ControlDebitosBancariosLiteFilter(ejercicio=2025)
            )

        self.assertEqual(upload_mock.call_count, 3)
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(
            hojas,
            ["siif_vs_sscc_db", "siif_db", "sscc_db"],
        )
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"],
                SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS,
            )


# -------------------------------------------------
class TestFiltrosControlDebitosBancarios(unittest.TestCase):
    """Los filtros conservan el contrato de las rutas."""

    # -------------------------------------------------
    def test_filter_convierte_ejercicio_a_int_para_mongo(self) -> None:
        """El query param llega como string del front y se compara como int."""
        filtro = ControlDebitosBancariosFilter(ejercicio="2025")

        self.assertEqual(filtro.get_full_filter(), {"ejercicio": 2025})

    # -------------------------------------------------
    def test_filter_sin_ejercicio_no_filtra(self) -> None:
        """Sin ejercicio (filtro limpio) el Get All no agrega restricción."""
        filtro = ControlDebitosBancariosFilter()

        self.assertEqual(filtro.get_full_filter(), {})

    # -------------------------------------------------
    def test_generate_filter_requiere_ejercicio(self) -> None:
        """/generate sin ejercicio debe rechazarse en la validación."""
        with self.assertRaises(ValidationError):
            ControlDebitosBancariosGenerateFilter()


# -------------------------------------------------
class TestRutasControlDebitosBancarios(unittest.TestCase):
    """La superficie de rutas expone snapshot CRUD (factory) + extras."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_debitos_bancarios_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlDebitosBancarios", "GET"),  # Get All (snapshot)
            ("/controlDebitosBancarios", "POST"),  # Add Many
            ("/controlDebitosBancarios", "DELETE"),  # Delete Many
            ("/controlDebitosBancarios/export", "GET"),  # Solo Google Sheets
            ("/controlDebitosBancarios/generate", "GET"),  # On-demand
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()