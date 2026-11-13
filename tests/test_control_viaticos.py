"""Tests del patrón generate -> POST de Control Viáticos (persistencia).

Cubre la paridad con los demás controles:

- ``generate`` delega el cómputo on-demand con el ``ejercicio``
  recibido (sin persistir).
- ``add_many`` congela el snapshot con borrado idempotente por
  ejercicio (clave ``[ejercicio, nro_expte]``).
- ``compute_control_rendicion`` arma el cruce (rfondos04 PA3/REV +
  gastos 372/373 + banco 029/040/005) y soporta lados vacíos.
- ``export`` solo sube a Google Sheets en background (sin Excel).
- Superficie de rutas: snapshot CRUD + ``/generate`` + ``/export``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_viaticos -v
"""

import asyncio
import unittest
from types import SimpleNamespace
from typing import Any, List
from unittest import mock

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from src.analysis.routes.control_viaticos import control_viaticos_router
from src.analysis.schemas import (
    ControlViaticosFilter,
    ControlViaticosGenerateFilter,
    ControlViaticosLiteFilter,
    ControlViaticosRendicionReport,
)
from src.analysis.services import ControlViaticosService
from src.analysis.services.control_viaticos import SPREADSHEET_KEY_CONTROL_VIATICOS


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 3) -> None:
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
def construir_servicio(repository: RepositorioFalso) -> ControlViaticosService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlViaticosService(
        control_rendicion_repo=repository,
        rfondos04_service=None,
        gastos_service=None,
        banco_service=None,
    )


# -------------------------------------------------
def fila_valida(ejercicio: int) -> dict:
    return {
        "ejercicio": ejercicio,
        "nro_expte": "9000012024",
        "siif_anticipo": 100.0,
        "siif_rendicion": 70.0,
        "siif_reversion": 30.0,
        "siif_saldo_anticipo": 0.0,
        "siif_reembolso": 10.0,
        "siif_gasto_total": 80.0,
        "sscc_anticipo": 100.0,
        "sscc_reversion": 0.0,
        "sscc_reembolso": 0.0,
        "sscc_gasto_total": 100.0,
        "dif_gasto_total": -20.0,
    }


# -------------------------------------------------
class TestGenerateControlViaticos(unittest.IsolatedAsyncioTestCase):
    """El endpoint /generate arma el cruce on-demand sin persistir."""

    # -------------------------------------------------
    async def test_generate_delega_en_compute(self) -> None:
        """generate llama a compute_control_rendicion con el ejercicio."""
        servicio = construir_servicio(RepositorioFalso())
        filas_esperadas = [fila_valida(2024)]

        with mock.patch.object(
            servicio,
            "compute_control_rendicion",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlViaticosGenerateFilter(ejercicio=2024)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2024)

    # -------------------------------------------------
    async def test_compute_requiere_ejercicio(self) -> None:
        """compute_control_rendicion avisa si falta el ejercicio."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlViaticosFilter(ejercicio=None)

        with self.assertRaises(ValueError):
            await servicio.compute_control_rendicion(params=params)


# -------------------------------------------------
class TestComputeControlViaticos(unittest.IsolatedAsyncioTestCase):
    """El cruce arma rfondos04 + gastos 372/373 + banco 029/040/005."""

    # -------------------------------------------------
    async def test_compute_cruce_happy_path(self) -> None:
        """Verifica las derivadas del cruce (saldo, gasto total, dif)."""
        servicio = construir_servicio(RepositorioFalso())
        fondos = pd.DataFrame(
            [
                {"nro_fondo": "F1", "tipo_comprobante": "PA3", "importe": 100.0},
                {"nro_fondo": "F1", "tipo_comprobante": "REV", "importe": 30.0},
            ]
        )
        banco = pd.DataFrame(
            [
                {
                    "nro_expte": "9000012024",
                    "cod_imputacion": "029",
                    "importe": 100.0,
                }
            ]
        )
        gastos = pd.DataFrame(
            [
                {
                    "ejercicio": 2024,
                    "nro_expte": "9000012024",
                    "nro_fondo": "F1",
                    "partida": "372",
                    "importe": 70.0,
                },
                {
                    "ejercicio": 2024,
                    "nro_expte": "9000012024",
                    "nro_fondo": None,
                    "partida": "373",
                    "importe": 10.0,
                },
            ]
        )

        with mock.patch.object(
            servicio,
            "generate_siif_fondo",
            new=mock.AsyncMock(return_value=fondos),
        ), mock.patch.object(
            servicio,
            "generate_banco",
            new=mock.AsyncMock(return_value=banco),
        ), mock.patch.object(
            servicio,
            "generate_siif_gastos",
            new=mock.AsyncMock(return_value=gastos),
        ):
            filas = await servicio.compute_control_rendicion(
                params=ControlViaticosFilter(ejercicio=2024)
            )

        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila["ejercicio"], 2024)
        self.assertEqual(fila["nro_expte"], "9000012024")
        self.assertEqual(fila["siif_anticipo"], 100.0)
        self.assertEqual(fila["siif_reversion"], 30.0)
        self.assertEqual(fila["siif_rendicion"], 70.0)
        self.assertEqual(fila["siif_reembolso"], 10.0)
        self.assertEqual(fila["siif_saldo_anticipo"], 0.0)  # 100 - 30 - 70
        self.assertEqual(fila["siif_gasto_total"], 80.0)  # 70 + 10
        self.assertEqual(fila["sscc_gasto_total"], 100.0)
        self.assertEqual(fila["dif_gasto_total"], -20.0)  # 80 - 100

    # -------------------------------------------------
    async def test_compute_con_lados_vacios_devuelve_vacio(self) -> None:
        """Sin datos de ningún sistema el cruce no truena y devuelve []."""
        servicio = construir_servicio(RepositorioFalso())

        with mock.patch.object(
            servicio,
            "generate_siif_fondo",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ), mock.patch.object(
            servicio,
            "generate_banco",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ), mock.patch.object(
            servicio,
            "generate_siif_gastos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ):
            filas = await servicio.compute_control_rendicion(
                params=ControlViaticosFilter(ejercicio=2024)
            )

        self.assertEqual(filas, [])


# -------------------------------------------------
class TestAddManyControlViaticos(unittest.IsolatedAsyncioTestCase):
    """POST /controlViaticos congela el snapshot (borrado por ejercicio)."""

    # -------------------------------------------------
    async def test_add_many_borra_por_ejercicio_y_persiste(self) -> None:
        repository = RepositorioFalso(filas_previas=3)
        servicio = construir_servicio(repository)

        resumen = await servicio.add_many(data=[fila_valida(2024)])

        self.assertEqual(resumen.deleted, 3)
        self.assertEqual(resumen.added, 1)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository.deleted_filters, [{"ejercicio": 2024}])
        self.assertFalse(repository.deleted_all_llamado)
        self.assertIsInstance(repository.saved[0], ControlViaticosRendicionReport)

    # -------------------------------------------------
    async def test_add_many_sin_filas_validas_lanza_400(self) -> None:
        """Si ninguna fila valida, add_many responde 400 y no persiste."""
        repository = RepositorioFalso()
        servicio = construir_servicio(repository)
        invalida = {"ejercicio": 2024, "nro_expte": "9000012024"}  # faltan importes

        with self.assertRaises(HTTPException) as ctx:
            await servicio.add_many(data=[invalida])

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No se encontraron registros válidos", ctx.exception.detail)
        self.assertEqual(len(repository.saved), 0)
        self.assertEqual(repository.deleted_filters, [])


# -------------------------------------------------
class TestExportControlViaticos(unittest.IsolatedAsyncioTestCase):
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
                params=ControlViaticosLiteFilter(ejercicio=2024),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_VIATICOS
        )
        self.assertIn("control_rendicion_db", respuesta["detail"])
        self.assertIn("siif_fondos_db", respuesta["detail"])
        self.assertIn("siif_gastos_db", respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_sube_tres_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube exactamente las 3 hojas pedidas."""
        servicio = construir_servicio(RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_viaticos."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_all",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_rendicion",
            new=mock.AsyncMock(return_value=[fila_valida(2024)]),
        ), mock.patch.object(
            servicio,
            "generate_siif_fondo",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ), mock.patch.object(
            servicio,
            "generate_siif_gastos",
            new=mock.AsyncMock(return_value=pd.DataFrame()),
        ):
            await servicio._export_to_google_sheets(
                params=ControlViaticosLiteFilter(ejercicio=2024)
            )

        self.assertEqual(upload_mock.call_count, 3)
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(
            hojas,
            ["control_rendicion_db_new", "siif_fondos_db_new", "siif_gastos_db_new"],
        )
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_VIATICOS
            )


# -------------------------------------------------
class TestFiltrosControlViaticos(unittest.TestCase):
    """Los filtros conservan el contrato de las rutas."""

    # -------------------------------------------------
    def test_filter_convierte_ejercicio_a_int_para_mongo(self) -> None:
        """El query param llega como string del front y se compara como int."""
        filtro = ControlViaticosFilter(ejercicio="2024")

        self.assertEqual(filtro.get_full_filter(), {"ejercicio": 2024})

    # -------------------------------------------------
    def test_filter_sin_ejercicio_no_filtra(self) -> None:
        """Sin ejercicio (filtro limpio) el Get All no agrega restricción."""
        filtro = ControlViaticosFilter()

        self.assertEqual(filtro.get_full_filter(), {})

    # -------------------------------------------------
    def test_generate_filter_requiere_ejercicio(self) -> None:
        """/generate sin ejercicio debe rechazarse en la validación."""
        with self.assertRaises(ValidationError):
            ControlViaticosGenerateFilter()


# -------------------------------------------------
class TestRutasControlViaticos(unittest.TestCase):
    """La superficie de rutas expone snapshot CRUD + generate + export."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_viaticos_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlViaticos", "GET"),  # Get All (snapshot persistido)
            ("/controlViaticos", "POST"),  # Add Many (congela el snapshot)
            ("/controlViaticos", "DELETE"),  # Delete Many
            ("/controlViaticos/generate", "GET"),  # Cruce on-demand
            ("/controlViaticos/export", "GET"),  # Solo Google Sheets
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()