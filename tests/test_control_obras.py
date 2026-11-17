"""Tests del patrón generate -> POST de Control Obras (persistencia del cruce).

Cubre la paridad con control_recursos:

- ``generate`` delega el cómputo on-demand en ``compute_control_obras``
  con el ``ejercicio`` recibido (sin persistir).
- ``add_many`` congela el snapshot con borrado idempotente por ejercicio.
- Los filtros exponen las rutas estándar del ``GenericRouterFactory``
  (Get All / Add Many / Delete / export) más las rutas propias
  (``/generate``, ``/compute``, ``/getIcaro``, ``/getSGF``).
- ``export`` solo sube a Google Sheets en background (sin Excel).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_obras -v
"""

import asyncio
import json
import unittest
from types import SimpleNamespace
from typing import Any, List
from unittest import mock

import pandas as pd
from fastapi import HTTPException
from pydantic import ValidationError

from src.analysis.routes.control_obras import control_obras_router
from src.analysis.schemas import (
    ControlObrasFullFilter,
    ControlObrasGenerateFilter,
    ControlObrasLiteFilter,
    ControlObrasReport,
)
from src.analysis.services import ControlObrasService
from src.analysis.services.control_obras import SPREADSHEET_KEY_CONTROL_OBRAS


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 3, filas: List[Any] = None) -> None:
        self.filas_previas = filas_previas
        self.deleted_filters: List[dict] = []
        self.deleted_all_llamado = False
        self.saved: List[Any] = []
        self.filas = filas if filas is not None else []

    # -------------------------------------------------
    async def count_by_fields(self, filters: dict) -> int:
        return self.filas_previas

    # -------------------------------------------------
    async def find_with_filter_params(self, params: Any) -> List[Any]:
        return list(self.filas)

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
def construir_servicio(repository: RepositorioFalso) -> ControlObrasService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlObrasService(
        repository=repository,
        resumen_rend_service=None,
        icaro_service=None,
        cta_cte_service=None,
    )


# -------------------------------------------------
def fila_valida(ejercicio: int, mes: str) -> dict:
    return {
        "ejercicio": ejercicio,
        "mes": mes,
        "cta_cte": "10158-8",
        "cuit": "30712345678",
        "ejecutado_icaro": 100.0,
        "bruto_sgf": 90.0,
        "diferencia": 10.0,
    }


# -------------------------------------------------
class TestGenerateControlObras(unittest.IsolatedAsyncioTestCase):
    """El endpoint /generate arma el cruce on-demand sin persistir."""

    # -------------------------------------------------
    async def test_generate_delega_en_compute_con_el_ejercicio(self) -> None:
        """Llama a compute_control_obras con el ejercicio y sin límite."""
        servicio = construir_servicio(RepositorioFalso())
        filas_esperadas = [fila_valida(2024, "01")]

        with mock.patch.object(
            servicio,
            "compute_control_obras",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlObrasGenerateFilter(ejercicio=2024)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2024)
        self.assertIsNone(params.limit)

    # -------------------------------------------------
    async def test_compute_requiere_ejercicio(self) -> None:
        """compute_control_obras avisa si falta el ejercicio (defensa)."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlObrasFullFilter(ejercicio=None)

        with self.assertRaises(ValueError):
            await servicio.compute_control_obras(params=params)


# -------------------------------------------------
class TestAddManyControlObras(unittest.IsolatedAsyncioTestCase):
    """POST /controlObras congela el snapshot (borrado por ejercicio)."""

    # -------------------------------------------------
    async def test_add_many_borra_por_ejercicio_y_persiste(self) -> None:
        """Borra solo las filas del ejercicio y guarda las validadas."""
        repository = RepositorioFalso(filas_previas=3)
        servicio = construir_servicio(repository)
        filas = [fila_valida(2024, "01"), fila_valida(2024, "02")]

        resumen = await servicio.add_many(data=filas)

        self.assertEqual(resumen.deleted, 3)
        self.assertEqual(resumen.added, 2)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository.deleted_filters, [{"ejercicio": 2024}])
        self.assertFalse(repository.deleted_all_llamado)
        self.assertEqual(len(repository.saved), 2)
        self.assertIsInstance(repository.saved[0], ControlObrasReport)

    # -------------------------------------------------
    async def test_add_many_reporta_filas_invalidas(self) -> None:
        """Las filas que no validan contra el schema quedan en errors."""
        repository = RepositorioFalso()
        servicio = construir_servicio(repository)
        valida = fila_valida(2024, "01")
        invalida = {"ejercicio": 2024, "mes": "02"}  # faltan campos

        resumen = await servicio.add_many(data=[valida, invalida])

        self.assertEqual(resumen.added, 1)
        self.assertEqual(len(resumen.errors), 1)
        self.assertEqual(len(repository.saved), 1)


# -------------------------------------------------
class TestFiltrosControlObras(unittest.TestCase):
    """Los filtros conservan el contrato de las rutas del factory."""

    # -------------------------------------------------
    def test_full_filter_convierte_ejercicio_a_int_para_mongo(self) -> None:
        """El query param llega como string del front y se compara como int."""
        filtro = ControlObrasFullFilter(ejercicio="2024")

        self.assertEqual(filtro.get_full_filter(), {"ejercicio": 2024})

    # -------------------------------------------------
    def test_full_filter_sin_ejercicio_no_filtra(self) -> None:
        """Sin ejercicio (filtro limpio) el Get All no agrega restricción."""
        filtro = ControlObrasFullFilter()

        self.assertEqual(filtro.get_full_filter(), {})

    # -------------------------------------------------
    def test_generate_filter_requiere_ejercicio(self) -> None:
        """/generate sin ejercicio debe rechazarse en la validación."""
        with self.assertRaises(ValidationError):
            ControlObrasGenerateFilter()


# -------------------------------------------------
class TestExportControlObras(unittest.IsolatedAsyncioTestCase):
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
                params=ControlObrasLiteFilter(ejercicio=2024),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_OBRAS
        )
        self.assertIn("control_mes_cta_cte_cuit_db", respuesta["detail"])
        self.assertIn("resumen_rend_cuit", respuesta["detail"])
        self.assertIn("icaro_carga_neto_rdeu", respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_requiere_ejercicio(self) -> None:
        """Sin ejercicio se responde 400 (no se encola nada)."""
        servicio = construir_servicio(RepositorioFalso())

        with self.assertRaises(HTTPException) as ctx:
            await servicio.export(params=ControlObrasLiteFilter())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ejercicio", ctx.exception.detail)

    # -------------------------------------------------
    async def test_export_sube_tres_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube las 3 hojas a GS sin construir XLS."""
        import src.analysis.services.control_obras as service_module

        # El módulo ya ni siquiera importa la respuesta binaria
        self.assertFalse(hasattr(service_module, "StreamingResponse"))

        servicio = construir_servicio(RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_obras."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_sgf_resumend_rend",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_icaro_carga_neto_rdeu",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_obras",
            new=mock.AsyncMock(return_value=[]),
        ):
            await servicio._export_to_google_sheets(
                params=ControlObrasLiteFilter(ejercicio=2024)
            )

        # Las 3 hojas subidas a Google Sheets, en el orden esperado
        self.assertEqual(upload_mock.call_count, 3)
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(
            hojas,
            [
                "control_mes_cta_cte_cuit_db",
                "resumen_rend_cuit",
                "icaro_carga_neto_rdeu",
            ],
        )
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"],
                SPREADSHEET_KEY_CONTROL_OBRAS,
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
                "cta_cte": ["10158-8", "334", None],
                "ejecutado_icaro": [100.5, float("nan"), 3.0],
                "bruto_sgf": [90.0, None, float("inf")],
            }
        )

        with mock.patch(
            "src.analysis.services.control_obras."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            ControlObrasService._build_df_and_upload(
                df, "control_mes_cta_cte_cuit_db"
            )

        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_mes_cta_cte_cuit_db")
        # Los id internos no viajan a la hoja
        self.assertNotIn("id", df_subido.columns)
        # Misma validación que hace gspread/requests al serializar
        json.dumps(df_subido.values.tolist(), allow_nan=False)
        self.assertIsNone(df_subido["cta_cte"].tolist()[2])
        self.assertIsNone(df_subido["ejecutado_icaro"].tolist()[1])
        self.assertIsNone(df_subido["bruto_sgf"].tolist()[2])


# -------------------------------------------------
class TestRutasControlObras(unittest.TestCase):
    """La superficie de rutas expone factory + rutas propias."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_obras_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlObras", "GET"),  # Get All (snapshot persistido)
            ("/controlObras", "POST"),  # Add Many (congela el snapshot)
            ("/controlObras", "DELETE"),  # Delete Many
            ("/controlObras/export", "GET"),
            ("/controlObras/generate", "GET"),  # Cruce on-demand
            ("/controlObras/compute", "GET"),  # Retrocompatibilidad
            ("/controlObras/getIcaro", "GET"),
            ("/controlObras/getSGF", "GET"),
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()