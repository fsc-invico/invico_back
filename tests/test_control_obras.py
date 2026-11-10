"""Tests del patrón generate -> POST de Control Obras (persistencia del cruce).

Cubre la paridad con control_recursos:

- ``generate`` delega el cómputo on-demand en ``compute_control_obras``
  con el ``ejercicio`` recibido (sin persistir).
- ``add_many`` congela el snapshot con borrado idempotente por ejercicio.
- Los filtros exponen las rutas estándar del ``GenericRouterFactory``
  (Get All / Add Many / Delete / export) más las rutas propias
  (``/generate``, ``/compute``, ``/getIcaro``, ``/getSGF``).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_obras -v
"""

import unittest
from types import SimpleNamespace
from typing import Any, List
from unittest import mock

from pydantic import ValidationError

from src.analysis.routes.control_obras import control_obras_router
from src.analysis.schemas import (
    ControlObrasFullFilter,
    ControlObrasGenerateFilter,
    ControlObrasReport,
)
from src.analysis.services import ControlObrasService


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