"""Tests del patrón generate -> POST de Control Haberes (persistencia).

Cubre la paridad con control_recursos / control_obras:

- ``generate`` delega el cómputo on-demand en ``compute_control_haberes``
  con el ``ejercicio`` recibido (sin persistir).
- ``add_many`` congela el snapshot con borrado idempotente por ejercicio
  (clave ``[ejercicio, mes]``).
- ``compute_control_haberes`` soporta lados vacíos (sin KeyError) para
  que "Omitir" sin crudos no truene.
- Los filtros exponen las rutas estándar del ``GenericRouterFactory``
  (Get All / Add Many / Delete / export) más las rutas propias
  (``/generate``, ``/compute``, ``/getSIIFHaberes``, ``/getBancoHaberes``).
- ``export`` solo sube a Google Sheets en background (sin Excel).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_haberes -v
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

from src.analysis.routes.control_haberes import control_haberes_router
from src.analysis.schemas import (
    ControlHaberesFullFilter,
    ControlHaberesGenerateFilter,
    ControlHaberesLiteFilter,
    ControlHaberesReport,
)
from src.analysis.services import ControlHaberesService
from src.analysis.services.control_haberes import (
    SPREADSHEET_KEY_CONTROL_HABERES,
)


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 4, filas: List[Any] = None) -> None:
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
def construir_servicio(repository: RepositorioFalso) -> ControlHaberesService:
    """Instancia el servicio con dependencias simuladas (dataclass)."""
    return ControlHaberesService(
        repository=repository,
        gastos_service=None,
        rdeu_service=None,
        contabilidad_service=None,
        cta_cte_service=None,
        banco_service=None,
    )


# -------------------------------------------------
def fila_valida(ejercicio: int, mes: str) -> dict:
    return {
        "ejercicio": ejercicio,
        "mes": mes,
        "ejecutado_siif": 100.0,
        "pagado_sscc": 90.0,
        "diferencia": 10.0,
        "dif_acum": 10.0,
    }


# -------------------------------------------------
class TestGenerateControlHaberes(unittest.IsolatedAsyncioTestCase):
    """El endpoint /generate arma el cruce on-demand sin persistir."""

    # -------------------------------------------------
    async def test_generate_delega_en_compute_con_el_ejercicio(self) -> None:
        """Llama a compute_control_haberes con el ejercicio y sin límite."""
        servicio = construir_servicio(RepositorioFalso())
        filas_esperadas = [fila_valida(2024, "01/2024")]

        with mock.patch.object(
            servicio,
            "compute_control_haberes",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlHaberesGenerateFilter(ejercicio=2024)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        params = compute_mock.await_args.kwargs["params"]
        self.assertEqual(params.ejercicio, 2024)
        self.assertIsNone(params.limit)

    # -------------------------------------------------
    async def test_compute_requiere_ejercicio(self) -> None:
        """compute_control_haberes avisa si falta el ejercicio (defensa)."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlHaberesFullFilter(ejercicio=None)

        with self.assertRaises(ValueError):
            await servicio.compute_control_haberes(params=params)

    # -------------------------------------------------
    async def test_compute_con_lados_vacios_no_truena(self) -> None:
        """Sin crudos SIIF ni SSCC el cruce devuelve [] (sin KeyError)."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlHaberesFullFilter(ejercicio=2024, limit=None)

        with mock.patch.object(
            servicio,
            "get_siif_comprobantes_haberes_neto_rdeu",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_banco_invico",
            new=mock.AsyncMock(return_value=[]),
        ):
            filas = await servicio.compute_control_haberes(params=params)

        self.assertEqual(filas, [])

    # -------------------------------------------------
    async def test_compute_solo_siif_rellena_sscc_en_cero(self) -> None:
        """Lado SSCC vacío: la diferencia usa 0 y el acumulado cuadra."""
        servicio = construir_servicio(RepositorioFalso())
        params = ControlHaberesFullFilter(ejercicio=2024, limit=None)
        siif = [
            {"ejercicio": 2024, "mes": "01/2024", "importe": 100.0},
            {"ejercicio": 2024, "mes": "01/2024", "importe": 50.0},
        ]

        with mock.patch.object(
            servicio,
            "get_banco_invico",
            new=mock.AsyncMock(return_value=[]),
        ):
            filas = await servicio.compute_control_haberes(
                params=params, siif=siif, sscc=[]
            )

        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila["ejecutado_siif"], 150.0)
        self.assertEqual(fila["pagado_sscc"], 0.0)
        self.assertEqual(fila["diferencia"], 150.0)
        self.assertEqual(fila["dif_acum"], 150.0)


# -------------------------------------------------
class TestAddManyControlHaberes(unittest.IsolatedAsyncioTestCase):
    """POST /controlHaberes congela el snapshot (borrado por ejercicio)."""

    # -------------------------------------------------
    async def test_add_many_borra_por_ejercicio_y_persiste(self) -> None:
        """Borra solo las filas del ejercicio y guarda las validadas."""
        repository = RepositorioFalso(filas_previas=4)
        servicio = construir_servicio(repository)
        filas = [fila_valida(2024, "01/2024"), fila_valida(2024, "02/2024")]

        resumen = await servicio.add_many(data=filas)

        self.assertEqual(resumen.deleted, 4)
        self.assertEqual(resumen.added, 2)
        self.assertEqual(resumen.errors, [])
        self.assertEqual(repository.deleted_filters, [{"ejercicio": 2024}])
        self.assertFalse(repository.deleted_all_llamado)
        self.assertEqual(len(repository.saved), 2)
        self.assertIsInstance(repository.saved[0], ControlHaberesReport)

    # -------------------------------------------------
    async def test_add_many_reporta_filas_invalidas(self) -> None:
        """Las filas que no validan contra el schema quedan en errors."""
        repository = RepositorioFalso()
        servicio = construir_servicio(repository)
        valida = fila_valida(2024, "01/2024")
        invalida = {"ejercicio": 2024, "mes": "02/2024"}  # faltan importes

        resumen = await servicio.add_many(data=[valida, invalida])

        self.assertEqual(resumen.added, 1)
        self.assertEqual(len(resumen.errors), 1)
        self.assertEqual(len(repository.saved), 1)


# -------------------------------------------------
class TestFiltrosControlHaberes(unittest.TestCase):
    """Los filtros conservan el contrato de las rutas del factory."""

    # -------------------------------------------------
    def test_full_filter_convierte_ejercicio_a_int_para_mongo(self) -> None:
        """El query param llega como string del front y se compara como int."""
        filtro = ControlHaberesFullFilter(ejercicio="2024")

        self.assertEqual(filtro.get_full_filter(), {"ejercicio": 2024})

    # -------------------------------------------------
    def test_full_filter_sin_ejercicio_no_filtra(self) -> None:
        """Sin ejercicio (filtro limpio) el Get All no agrega restricción."""
        filtro = ControlHaberesFullFilter()

        self.assertEqual(filtro.get_full_filter(), {})

    # -------------------------------------------------
    def test_generate_filter_requiere_ejercicio(self) -> None:
        """/generate sin ejercicio debe rechazarse en la validación."""
        with self.assertRaises(ValidationError):
            ControlHaberesGenerateFilter()


# -------------------------------------------------
class TestExportControlHaberes(unittest.IsolatedAsyncioTestCase):
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
                params=ControlHaberesLiteFilter(ejercicio=2024),
            )
            # Deja avanzar la tarea encolada en el event loop
            await asyncio.sleep(0)

        self.assertIsInstance(respuesta, dict)
        self.assertEqual(respuesta["title"], "Exportación a Google Sheets iniciada")
        self.assertEqual(
            respuesta["spreadsheet_key"], SPREADSHEET_KEY_CONTROL_HABERES
        )
        self.assertIn("siif_comprobantes_haberes_db", respuesta["detail"])
        self.assertIn("sscc_haberes_db", respuesta["detail"])
        self.assertIn("control_mensual_db", respuesta["detail"])
        tarea_mock.assert_awaited_once()

    # -------------------------------------------------
    async def test_export_requiere_ejercicio(self) -> None:
        """Sin ejercicio se responde 400 (no se encola nada)."""
        servicio = construir_servicio(RepositorioFalso())

        with self.assertRaises(HTTPException) as ctx:
            await servicio.export(params=ControlHaberesLiteFilter())

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("ejercicio", ctx.exception.detail)

    # -------------------------------------------------
    async def test_export_sube_tres_hojas_sin_excel(self) -> None:
        """La tarea de fondo sube las 3 hojas a GS sin construir XLS."""
        import src.analysis.services.control_haberes as service_module

        # El módulo ya ni siquiera importa la respuesta binaria
        self.assertFalse(hasattr(service_module, "StreamingResponse"))

        servicio = construir_servicio(RepositorioFalso())
        with mock.patch(
            "src.analysis.services.control_haberes."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock, mock.patch.object(
            servicio,
            "get_siif_comprobantes_haberes_neto_rdeu",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "get_banco_invico",
            new=mock.AsyncMock(return_value=[]),
        ), mock.patch.object(
            servicio,
            "compute_control_haberes",
            new=mock.AsyncMock(return_value=[]),
        ):
            await servicio._export_to_google_sheets(
                params=ControlHaberesLiteFilter(ejercicio=2024)
            )

        # Las 3 hojas subidas a Google Sheets, en el orden esperado
        self.assertEqual(upload_mock.call_count, 3)
        hojas = [call.args[0][0][1] for call in upload_mock.call_args_list]
        self.assertEqual(
            hojas,
            [
                "siif_comprobantes_haberes_db",
                "sscc_haberes_db",
                "control_mensual_db",
            ],
        )
        for call in upload_mock.call_args_list:
            self.assertEqual(
                call.kwargs["spreadsheet_key"],
                SPREADSHEET_KEY_CONTROL_HABERES,
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
                "mes": ["01", "02", None],
                "ejecutado_siif": [100.5, float("nan"), 3.0],
                "pagado_sscc": [90.0, None, float("inf")],
            }
        )

        with mock.patch(
            "src.analysis.services.control_haberes."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            ControlHaberesService._build_df_and_upload(
                df, "control_mensual_db"
            )

        df_subido = upload_mock.call_args.args[0][0][0]
        hoja = upload_mock.call_args.args[0][0][1]
        self.assertEqual(hoja, "control_mensual_db")
        # Los id internos no viajan a la hoja
        self.assertNotIn("id", df_subido.columns)
        # Misma validación que hace gspread/requests al serializar
        json.dumps(df_subido.values.tolist(), allow_nan=False)
        self.assertIsNone(df_subido["mes"].tolist()[2])
        self.assertIsNone(df_subido["ejecutado_siif"].tolist()[1])
        self.assertIsNone(df_subido["pagado_sscc"].tolist()[2])


# -------------------------------------------------
class TestRutasControlHaberes(unittest.TestCase):
    """La superficie de rutas expone factory + rutas propias."""

    # -------------------------------------------------
    def test_rutas_registradas(self) -> None:
        rutas = {
            (ruta.path, metodo)
            for ruta in control_haberes_router.routes
            for metodo in ruta.methods
        }

        esperadas = {
            ("/controlHaberes", "GET"),  # Get All (snapshot persistido)
            ("/controlHaberes", "POST"),  # Add Many (congela el snapshot)
            ("/controlHaberes", "DELETE"),  # Delete Many
            ("/controlHaberes/export", "GET"),
            ("/controlHaberes/generate", "GET"),  # Cruce on-demand
            ("/controlHaberes/compute", "GET"),  # Retrocompatibilidad
            ("/controlHaberes/getSIIFHaberes", "GET"),
            ("/controlHaberes/getBancoHaberes", "GET"),
        }
        faltantes = esperadas - rutas

        self.assertFalse(faltantes, f"Faltan rutas: {sorted(faltantes)}")


if __name__ == "__main__":
    unittest.main()