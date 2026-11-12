"""Tests del patrón generate -> POST de Control Honorarios (persistencia).

Módulo dual: dos reportes con sus propias colecciones.

- ``generate_siif_vs_slave`` / ``generate_sgf_vs_slave`` delegan el
  cómputo on-demand con el ``ejercicio`` recibido (sin persistir).
- ``add_many_siif_vs_slave`` / ``add_many_sgf_vs_slave`` congelan cada
  snapshot con borrado idempotente por ejercicio.
- La superficie de rutas expone los endpoints de snapshot
  (``/siifVsSlave`` y ``/sgfVsSlave``) más los ``/generate*`` y las
  rutas de crudo/compute existentes.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_honorarios -v
"""

import unittest
from types import SimpleNamespace
from typing import Any, List
from unittest import mock

from fastapi import BackgroundTasks
from pydantic import ValidationError

from src.analysis.routes.control_honorarios import control_honorarios_router
from src.analysis.schemas import (
    ControlHonorariosFullFilter,
    ControlHonorariosGenerateFilter,
    ControlHonorariosLiteFilter,
    ControlHonorariosSGFvsSlaveReport,
    ControlHonorariosSIIFvsSlaveReport,
)
from src.analysis.services import ControlHonorariosService
from src.analysis.services.control_honorarios import SPREADSHEET_KEY_CONTROL_HONORARIOS


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 2) -> None:
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
def construir_servicio(
    siif_repository: RepositorioFalso, sgf_repository: RepositorioFalso
) -> ControlHonorariosService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlHonorariosService(
        siif_vs_slave_repository=siif_repository,
        sgf_vs_slave_repository=sgf_repository,
        gastos_service=None,
        slave_service=None,
        sgf_service=None,
        banco_service=None,
        cta_cte_service=None,
    )


# -------------------------------------------------
def fila_siif_valida(ejercicio: int) -> dict:
    return {
        "ejercicio": ejercicio,
        "siif_nro": "00123",
        "slave_nro": "00124",
        "err_nro": True,
        "siif_importe": 100.0,
        "slave_importe": 90.0,
        "err_importe": True,
        "siif_mes": "01/2024",
        "slave_mes": "02/2024",
        "err_mes": True,
    }


# -------------------------------------------------
def fila_sgf_valida(ejercicio: int) -> dict:
    return {
        "ejercicio": ejercicio,
        "mes": "01/2024",
        "cta_cte": "130832-05",
        "beneficiario": "PY A",
        "sgf_importe_bruto": 100.0,
        "slave_importe_bruto": 90.0,
        "dif_importe_bruto": 10.0,
        "sgf_importe_neto": 85.0,
        "slave_importe_neto": 80.0,
        "dif_importe_neto": 5.0,
    }


# -------------------------------------------------
class TestGenerateControlHonorarios(unittest.IsolatedAsyncioTestCase):
    """Los endpoints /generate* arman el cruce on-demand sin persistir."""

    # -------------------------------------------------
    async def test_generate_siif_delega_en_compute(self) -> None:
        """generate_siif_vs_slave llama al compute con el ejercicio."""
        servicio = construir_servicio(RepositorioFalso(), RepositorioFalso())
        filas_esperadas = [fila_siif_valida(2024)]

        with mock.patch.object(
            servicio,
            "compute_control_siif_vs_slave",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate_siif_vs_slave(
                ControlHonorariosGenerateFilter(ejercicio=2024)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2024)
        self.assertIsNone(params.limit)

    # -------------------------------------------------
    async def test_generate_sgf_delega_en_compute(self) -> None:
        """generate_sgf_vs_slave llama al compute con el ejercicio."""
        servicio = construir_servicio(RepositorioFalso(), RepositorioFalso())
        filas_esperadas = [fila_sgf_valida(2024)]

        with mock.patch.object(
            servicio,
            "compute_control_sgf_vs_slave",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate_sgf_vs_slave(
                ControlHonorariosGenerateFilter(ejercicio=2024)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2024)

    # -------------------------------------------------
    async def test_compute_siif_requiere_ejercicio(self) -> None:
        """compute_control_siif_vs_slave avisa si falta el ejercicio."""
        servicio = construir_servicio(RepositorioFalso(), RepositorioFalso())
        params = ControlHonorariosFullFilter(ejercicio=None)

        with self.assertRaises(ValueError):
            await servicio.compute_control_siif_vs_slave(params=params)


# -------------------------------------------------
class TestAddManyControlHonorarios(unittest.IsolatedAsyncioTestCase):
    """Cada POST congela su snapshot con borrado por ejercicio."""

    # -------------------------------------------------
    async def test_add_many_siif_borra_por_ejercicio_y_persiste(self) -> None:
        repository_siif = RepositorioFalso(filas_previas=2)
        servicio = construir_servicio(repository_siif, RepositorioFalso())

        resumen = await servicio.add_many_siif_vs_slave(data=[fila_siif_valida(2024)])

        self.assertEqual(resumen.deleted, 2)
        self.assertEqual(resumen.added, 1)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository_siif.deleted_filters, [{"ejercicio": 2024}])
        self.assertFalse(repository_siif.deleted_all_llamado)
        self.assertIsInstance(
            repository_siif.saved[0], ControlHonorariosSIIFvsSlaveReport
        )

    # -------------------------------------------------
    async def test_add_many_sgf_borra_por_ejercicio_y_persiste(self) -> None:
        repository_sgf = RepositorioFalso(filas_previas=5)
        servicio = construir_servicio(RepositorioFalso(), repository_sgf)

        resumen = await servicio.add_many_sgf_vs_slave(data=[fila_sgf_valida(2024)])

        self.assertEqual(resumen.deleted, 5)
        self.assertEqual(resumen.added, 1)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository_sgf.deleted_filters, [{"ejercicio": 2024}])
        self.assertIsInstance(
            repository_sgf.saved[0], ControlHonorariosSGFvsSlaveReport
        )

    # -------------------------------------------------
    async def test_add_many_reporta_filas_invalidas(self) -> None:
        """Las filas que no validan contra el schema quedan en errors."""
        repository_siif = RepositorioFalso()
        servicio = construir_servicio(repository_siif, RepositorioFalso())
        invalida = {"ejercicio": 2024, "siif_nro": "1"}  # faltan campos

        resumen = await servicio.add_many_siif_vs_slave(data=[invalida])

        self.assertEqual(resumen.added, 0)
        self.assertEqual(len(resumen.errors), 1)
        self.assertEqual(len(repository_siif.saved), 0)


# -------------------------------------------------
class TestFiltrosControlHonorarios(unittest.TestCase):
    """Los filtros conservan el contrato de las rutas."""

    # -------------------------------------------------
    def test_full_filter_convierte_ejercicio_a_int_para_mongo(self) -> None:
        """El query param llega como string del front y se compara como int."""
        filtro = ControlHonorariosFullFilter(ejercicio="2024")

        self.assertEqual(filtro.get_full_filter(), {"ejercicio": 2024})

    # -------------------------------------------------
    def test_full_filter_sin_ejercicio_no_filtra(self) -> None:
        """Sin ejercicio (filtro limpio) el Get All no agrega restricción."""
        filtro = ControlHonorariosFullFilter()

        self.assertEqual(filtro.get_full_filter(), {})

    # -------------------------------------------------
    def test_generate_filter_requiere_ejercicio(self) -> None:
        """/generate* sin ejercicio debe rechazarse en la validación."""
        with self.assertRaises(ValidationError):
            ControlHonorariosGenerateFilter()


# -------------------------------------------------
class TestRutasControlHonorarios(unittest.TestCase):
    """La superficie de rutas expone snapshots + generates + crudos."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_honorarios_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            # Snapshots por reporte (persistencia)
            ("/controlHonorarios/siifVsSlave", "GET"),
            ("/controlHonorarios/siifVsSlave", "POST"),
            ("/controlHonorarios/siifVsSlave", "DELETE"),
            ("/controlHonorarios/sgfVsSlave", "GET"),
            ("/controlHonorarios/sgfVsSlave", "POST"),
            ("/controlHonorarios/sgfVsSlave", "DELETE"),
            # Cruces on-demand
            ("/controlHonorarios/generateSIIFVsSlave", "GET"),
            ("/controlHonorarios/generateSGFVsSlave", "GET"),
            # Rutas existentes (retrocompatibilidad)
            ("/controlHonorarios/computeSIIFVsSlave", "GET"),
            ("/controlHonorarios/computeSGFVsSlave", "GET"),
            ("/controlHonorarios/getSIIFHonorarios", "GET"),
            ("/controlHonorarios/getSGFHonorarios", "GET"),
            ("/controlHonorarios/getSlaveHonorarios", "GET"),
            ("/controlHonorarios/export", "GET"),
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


# -------------------------------------------------
class TestExportControlHonorarios(unittest.IsolatedAsyncioTestCase):
    """El export solo sube a Google Sheets (sin Excel), en background."""

    # -------------------------------------------------
    async def test_export_encola_gs_y_responde_json(self) -> None:
        """Responde JSON de inmediato y encola el trabajo pesado."""
        servicio = construir_servicio(RepositorioFalso(), RepositorioFalso())
        background_tasks = BackgroundTasks()
        params = ControlHonorariosLiteFilter(ejercicio=2024)

        respuesta = await servicio.export(
            params=params, background_tasks=background_tasks
        )

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_HONORARIOS
        )
        # El trabajo pesado (queries + upload) queda encolado: no corre
        # dentro del request, por lo que no bloqueia el event loop.
        self.assertEqual(len(background_tasks.tasks), 1)

    # -------------------------------------------------
    async def test_export_no_genera_excel(self) -> None:
        """La tarea de fondo sube las 5 hojas a GS sin construir XLS."""
        import src.analysis.services.control_honorarios as service_module

        # El módulo ya ni siquiera importa el generador de Excel
        self.assertFalse(
            hasattr(service_module, "export_multiple_dataframes_to_excel")
        )

        servicio = construir_servicio(RepositorioFalso(), RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_honorarios."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_siif_honorarios",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_slave_honorarios",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_sgf_honorarios",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_snapshot_siif_vs_slave",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_snapshot_sgf_vs_slave",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_siif_vs_slave",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_sgf_vs_slave",
            new=mock.AsyncMock(return_value=[]),
        ):
            await servicio._export_to_google_sheets(
                params=ControlHonorariosLiteFilter(ejercicio=2024)
            )

        # Las 5 hojas subidas a Google Sheets, en el orden esperado
        self.assertEqual(upload_mock.call_count, 5)
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(
            hojas,
            [
                "siif_vs_slave_db",
                "sgf_vs_slave_db",
                "siif_db",
                "slave_db",
                "sgf_db",
            ],
        )
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_HONORARIOS
            )


if __name__ == "__main__":
    unittest.main()