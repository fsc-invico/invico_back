"""Tests del nuevo control "Otros Gastos" (lo que quedó por fuera de
los demás controles).

Cubre:

- ``compute_otros_gastos_siif``: cada paso de depuración (es_aprobado,
  MAP + positivo revierto, fondos regularizados por PA6, obras Icaro
  REG/CYO, haberes, honorarios SIIF ∪ Slave, viáticos por
  nro_comprobante/nro_expte y débitos bancarios) deja SOLO el resto.
- ``compute_otros_gastos_sgf``: dedup + exclusiones de obras,
  honorarios y escribanos.
- ``generate`` delega el cómputo on-demand con el ``ejercicio``
  recibido (sin persistir) y ``add_many`` congela el snapshot con
  borrado idempotente por ejercicio en AMBOS lados.
- Superficie de rutas: 2 conjuntos (``/otrosGastos/siif`` y
  ``/otrosGastos/sgf``) con Get All / Add Many / Delete / ``/generate``
  y UNA sola ruta de export unificada (``/otrosGastos/export``): los
  ``/export`` por lado del factory no existen.
- ``export`` unificado: 400 mientras la key del Google Sheet esté vacía
  y subida de las 2 hojas al MISMO key (snapshot + fallback).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_otros_gastos -v
"""

import unittest
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest import mock

import pandas as pd
from fastapi import HTTPException

from src.analysis.routes.control_otros_gastos import (
    control_otros_gastos_router,
    control_otros_gastos_sgf_router,
    control_otros_gastos_siif_router,
)
from src.analysis.schemas import (
    ControlOtrosGastosExportFilter,
    ControlOtrosGastosGenerateFilter,
    ControlOtrosGastosSgfReport,
    ControlOtrosGastosSgfFilter,
    ControlOtrosGastosSiifFilter,
    ControlOtrosGastosSiifReport,
)
from src.analysis.services import (
    ControlOtrosGastosExportService,
    ControlOtrosGastosSgfService,
    ControlOtrosGastosSiifService,
)
from src.analysis.services.control_otros_gastos import HOJA_SGF, HOJA_SIIF


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(self, filas_previas: int = 4) -> None:
        self.filas_previas = filas_previas
        self.deleted_filters: List[dict] = []
        self.deleted_all_llamado = False
        self.saved: List[Any] = []

    # --------------------------------------------------
    async def count_by_fields(self, filters: dict) -> int:
        return self.filas_previas

    # --------------------------------------------------
    async def delete_by_fields(self, filters: dict) -> int:
        self.deleted_filters.append(filters)
        return self.filas_previas

    # --------------------------------------------------
    async def delete_all(self) -> int:
        self.deleted_all_llamado = True
        return 0

    # --------------------------------------------------
    async def save_all(self, validated: List[Any]) -> SimpleNamespace:
        self.saved.extend(validated)
        return SimpleNamespace(inserted_ids=list(range(len(validated))))


# --------------------------------------------------
class GastosFalso:
    """Devuelve las filas de gto_rpa03g ⟕ rcg01_uejp."""

    def __init__(self, filas: List[dict]) -> None:
        self.filas = filas

    # --------------------------------------------------
    async def get_joined_with_rcg01_uejp(self, params: Any) -> List[dict]:
        return self.filas


# --------------------------------------------------
class Rcg01Falso:
    def __init__(self, mapas: List[Any]) -> None:
        self.mapas = mapas

    # --------------------------------------------------
    async def get_all(self, params: Any) -> List[Any]:
        return self.mapas


# --------------------------------------------------
class CargaFalso:
    def __init__(self, documentos: List[Any]) -> None:
        self.documentos = documentos

    # --------------------------------------------------
    async def get_all(self, params: Any) -> List[Any]:
        return self.documentos


# --------------------------------------------------
class Rfondo07tpFalso:
    """Devuelve los comprobantes PA6 de siif_rfondo07tp."""

    def __init__(self, documentos: List[Any]) -> None:
        self.documentos = documentos

    # --------------------------------------------------
    async def get_all(self, params: Any) -> List[Any]:
        return self.documentos


# --------------------------------------------------
class HonorariosFalso:
    # --------------------------------------------------
    async def get_slave_honorarios(self, params: Any) -> List[dict]:
        return [{"nro_comprobante": "00007/05"}]


# --------------------------------------------------
class CtaCteFalso:
    """Unifier passthrough: los tests no usan el nexo real."""

    # --------------------------------------------------
    async def cta_cte_unifier(
        self, original_df: pd.DataFrame, cta_cte_nexo: str
    ) -> pd.DataFrame:
        return original_df


# --------------------------------------------------
class ViaticosFalso:
    # --------------------------------------------------
    async def generate_siif_gastos(self, ejercicio: int) -> pd.DataFrame:
        return pd.DataFrame(
            [{"nro_comprobante": "00008/05", "nro_expte": "EXP-100"}]
        )


# --------------------------------------------------
class DebitosFalso:
    # --------------------------------------------------
    async def generate_siif_debitos(self, ejercicio: int) -> pd.DataFrame:
        return pd.DataFrame([{"nro_comprobante": "00009/05"}])


# --------------------------------------------------
def fila_siif(
    nro_comprobante: str,
    nro_entrada: str,
    es_aprobado: Any = True,
    clase_mod: str = "NOR",
    clase_reg: str = "REG",
    clase_gto: str = "REM",
    nro_expte: str = "EXP-0",
    nro_fondo: Optional[str] = None,
    cta_cte: str = "130101-01",
    cuit: str = "20223334445",
    grupo: str = "4",
    partida: str = "421",
    glosa: str = "",
) -> dict:
    return {
        "ejercicio": 2026,
        "mes": "05/2026",
        "fecha": "01/05/2026",
        "nro_comprobante": nro_comprobante,
        "importe": 100.0,
        "cta_cte": cta_cte,
        "cuit": cuit,
        "beneficiario": "PROVEEDOR SA",
        "clase_reg": clase_reg,
        "clase_mod": clase_mod,
        "clase_gto": clase_gto,
        "es_comprometido": True,
        "es_verificado": True,
        "es_aprobado": es_aprobado,
        "es_pagado": True,
        "nro_entrada": nro_entrada,
        "nro_expte": nro_expte,
        "nro_fondo": nro_fondo,
        "partida": partida,
        "grupo": grupo,
        "glosa": glosa,
    }


# --------------------------------------------------
def fila_sgf(
    libramiento: str,
    origen: str = "FUNCIONAMIENTO",
    destino: str = "PROVEEDORES - FUNCIONAMIENTO",
    cta_cte: str = "130101-01",
) -> dict:
    return {
        "origen": origen,
        "ejercicio": 2026,
        "mes": "05/2026",
        "fecha": "01/05/2026",
        "beneficiario": "PROVEEDOR SA",
        "destino": destino,
        "libramiento": libramiento,
        "movimiento": "CHEQUE",
        "cta_cte": cta_cte,
        "importe_bruto": 100.0,
        "gcias": 0.0,
        "sellos": 0.0,
        "iibb": 0.0,
        "suss": 0.0,
        "invico": 0.0,
        "seguro": 0.0,
        "salud": 0.0,
        "mutual": 0.0,
        "otras": 0.0,
        "retenciones": 0.0,
        "importe_neto": 100.0,
        "cuit": "20223334445",
    }


# --------------------------------------------------
def construir_servicio_siif(
    gastos: GastosFalso,
    repository: Optional[RepositorioFalso] = None,
    rfondo07tp: Optional[Rfondo07tpFalso] = None,
) -> ControlOtrosGastosSiifService:
    """Instancia el servicio SIIF con dependencias simuladas (dataclass)."""
    return ControlOtrosGastosSiifService(
        repository=repository or RepositorioFalso(),
        gastos_service=gastos,
        rcg01_service=Rcg01Falso(
            [SimpleNamespace(nro_comprobante="00003/05", nro_origen="00004")]
        ),
        rfondo07tp_service=rfondo07tp or Rfondo07tpFalso([]),
        icaro_carga_service=CargaFalso(
            [SimpleNamespace(nro_comprobante="00002/05")]
        ),
        honorarios_service=HonorariosFalso(),
        viaticos_service=ViaticosFalso(),
        debitos_service=DebitosFalso(),
        cta_cte_service=CtaCteFalso(),
    )


# --------------------------------------------------
class TestComputeOtrosGastosSiif(unittest.IsolatedAsyncioTestCase):
    """compute_otros_gastos_siif deja SOLO lo no cubierto por controles."""

    # --------------------------------------------------
    async def test_depuracion_completa(self) -> None:
        """Cada paso descuenta su conjunto y solo queda la fila 'ok'."""
        base = [
            fila_siif("00001/05", "00001"),  # sobrevive
            fila_siif("00100/05", "00100", es_aprobado=False),  # no aprobado
            fila_siif("00101/05", "00101", es_aprobado=None),  # sin rcg01
            fila_siif("00003/05", "00003", clase_mod="MAP"),  # MAP
            fila_siif("00004/05", "00004"),  # positivo revertido (MAP)
            fila_siif("00002/05", "00002"),  # obra Icaro
            fila_siif("00005/05", "00005", cta_cte="130832-04"),  # haberes
            fila_siif(  # honorarios SIIF (criterio completo)
                "00006/05",
                "00006",
                cta_cte="130832-05",
                cuit="30632351514",
                grupo="3",
                glosa="HONORARIOS PROFESIONALES Y ASISTENTES SOCIALES",
            ),
            fila_siif("00007/05", "00007"),  # honorarios Slave
            fila_siif("00008/05", "00008"),  # viáticos (nro_comprobante)
            fila_siif("00102/05", "00102", nro_expte="EXP-100"),  # viáticos
            fila_siif("00009/05", "00009"),  # débitos bancarios
            fila_siif(  # ART (REM + partida 151)
                "00010/05", "00010", partida="151", grupo="1"
            ),
            fila_siif(  # caja chica (REG + fondo + cuit ≠ INVICO)
                "00011/05", "00011", nro_fondo="77"
            ),
        ]
        servicio = construir_servicio_siif(GastosFalso(base))

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )

        nros = [fila["nro_comprobante"] for fila in resultado]
        self.assertEqual(nros, ["00001/05"])

    # --------------------------------------------------
    async def test_depuracion_fondos_pa6(self) -> None:
        """Solo los REG cuyo nro_fondo es de un PA6 del ejercicio salen."""
        base = [
            fila_siif("00020/05", "00020", nro_fondo="97"),  # fondo PA6
            fila_siif(  # otro fondo (cuit INVICO: fondos permanentes,
                #              no caja chica → aisla el test del paso 11)
                "00021/05",
                "00021",
                nro_fondo="42",
                cuit="30632351514",
            ),
            fila_siif(  # no REG: CYO con fondo PA6
                "00022/05", "00022", nro_fondo="97", clase_reg="CYO"
            ),
            fila_siif("00023/05", "00023"),  # REG sin nro_fondo
            fila_siif(  # comparación literal: "00097" ≠ "97" → queda
                "00024/05",
                "00024",
                nro_fondo="00097",
                cuit="30632351514",
            ),
        ]
        servicio = construir_servicio_siif(
            GastosFalso(base),
            rfondo07tp=Rfondo07tpFalso([SimpleNamespace(nro_fondo="97")]),
        )

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )

        nros = [fila["nro_comprobante"] for fila in resultado]
        self.assertEqual(
            nros, ["00021/05", "00022/05", "00023/05", "00024/05"]
        )

    # --------------------------------------------------
    async def test_depuracion_art(self) -> None:
        """Sale solo REM con partida 151; 151 sin REM y 421 REM quedan."""
        base = [
            fila_siif(  # ART: clase_gto REM + partida 151
                "00030/05", "00030", partida="151", grupo="1"
            ),
            fila_siif(  # 151 pero NO REM → queda
                "00031/05",
                "00031",
                partida="151",
                grupo="1",
                clase_gto="PRE",
            ),
            fila_siif("00032/05", "00032"),  # 421 REM → queda
        ]
        servicio = construir_servicio_siif(GastosFalso(base))

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )

        nros = [fila["nro_comprobante"] for fila in resultado]
        self.assertEqual(nros, ["00031/05", "00032/05"])

    # --------------------------------------------------
    async def test_depuracion_cajas_chicas(self) -> None:
        """Sale solo REG con nro_fondo cargado y cuit ≠ INVICO."""
        base = [
            fila_siif(  # caja chica: REG + fondo + cuit ≠ INVICO
                "00040/05", "00040", nro_fondo="77"
            ),
            fila_siif(  # fondos permanentes (cuit INVICO) → queda
                "00041/05", "00041", nro_fondo="77", cuit="30632351514"
            ),
            fila_siif("00042/05", "00042"),  # sin fondo cargado → queda
            fila_siif(  # fondo en 0 → queda
                "00043/05", "00043", nro_fondo="0"
            ),
            fila_siif(  # no es REG → queda
                "00044/05", "00044", nro_fondo="77", clase_reg="CYO"
            ),
        ]
        servicio = construir_servicio_siif(GastosFalso(base))

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )

        nros = [fila["nro_comprobante"] for fila in resultado]
        self.assertEqual(
            nros, ["00041/05", "00042/05", "00043/05", "00044/05"]
        )

    # --------------------------------------------------
    async def test_sin_datos_devuelve_vacio(self) -> None:
        """Sin filas de gto/rcg01 devuelve [] sin tocar el resto."""
        servicio = construir_servicio_siif(GastosFalso([]))

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )
        self.assertEqual(resultado, [])

    # --------------------------------------------------
    async def test_generate_delega_en_compute(self) -> None:
        """generate llama a compute con el ejercicio recibido."""
        servicio = construir_servicio_siif(GastosFalso([]))
        filas_esperadas = [{"nro_comprobante": "00001/05"}]

        with mock.patch.object(
            servicio,
            "compute_otros_gastos_siif",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlOtrosGastosGenerateFilter(ejercicio=2026)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        parametros = compute_mock.await_args.kwargs["params"]
        self.assertEqual(parametros.ejercicio, 2026)

    # --------------------------------------------------
    async def test_generate_sin_ejercicio_lanza_value_error(self) -> None:
        servicio = construir_servicio_siif(GastosFalso([]))
        with self.assertRaises(ValueError):
            await servicio.generate(
                ControlOtrosGastosGenerateFilter.model_construct(ejercicio=None)
            )


# --------------------------------------------------
class ResumenRendFalso:
    def __init__(self, filas: List[dict]) -> None:
        self.filas = filas

    # --------------------------------------------------
    async def drop_duplicates_optimizado(self, params: Any) -> List[dict]:
        return self.filas


# --------------------------------------------------
class TestComputeOtrosGastosSgf(unittest.IsolatedAsyncioTestCase):
    """compute_otros_gastos_sgf deja SOLO lo no cubierto por controles."""

    # --------------------------------------------------
    async def test_depuracion_completa(self) -> None:
        """Remueve obras, honorarios y escribanos; conserva el resto."""
        base = [
            # Queda: proveedores de FUNCIONAMIENTO
            fila_sgf("L-1"),
            # control_obras: origen OBRAS
            fila_sgf("L-2", origen="OBRAS"),
            # control_obras: EPAM sin honorarios
            fila_sgf(
                "L-3",
                origen="EPAM",
                destino="OBRAS - EPAM",
            ),
            # control_honorarios: EPAM de honorarios en cta 07
            fila_sgf(
                "L-4",
                origen="EPAM",
                destino="HONORARIOS - EPAM",
                cta_cte="130832-07",
            ),
            # control_honorarios: FUNCIONAMIENTO de honorarios cta 05
            fila_sgf(
                "L-5",
                destino="HONORARIOS - FUNCIONAMIENTO",
                cta_cte="130832-05",
            ),
            # control_escribanos: cta_cte 130832-08
            fila_sgf("L-6", destino="ESCRIBANOS", cta_cte="130832-08"),
            # Queda: honorarios EPAM en cuenta fuera del control
            fila_sgf(
                "L-7",
                origen="EPAM",
                destino="HONORARIOS - EPAM",
                cta_cte="130832-99",
            ),
        ]
        servicio = ControlOtrosGastosSgfService(
            repository=RepositorioFalso(),
            resumen_rend_service=ResumenRendFalso(base),
            cta_cte_service=CtaCteFalso(),
        )

        resultado = await servicio.compute_otros_gastos_sgf(
            params=ControlOtrosGastosSgfFilter(ejercicio=2026, limit=None)
        )

        libramientos = [fila["libramiento"] for fila in resultado]
        self.assertEqual(libramientos, ["L-1", "L-7"])

    # --------------------------------------------------
    async def test_generate_delega_en_compute(self) -> None:
        servicio = ControlOtrosGastosSgfService(
            repository=RepositorioFalso(),
            resumen_rend_service=ResumenRendFalso([]),
            cta_cte_service=CtaCteFalso(),
        )
        filas_esperadas = [{"libramiento": "L-1"}]

        with mock.patch.object(
            servicio,
            "compute_otros_gastos_sgf",
            new=mock.AsyncMock(return_value=filas_esperadas),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlOtrosGastosGenerateFilter(ejercicio=2026)
            )

        self.assertEqual(resultado, filas_esperadas)
        compute_mock.assert_awaited_once()
        parametros = compute_mock.await_args.kwargs["params"]
        self.assertEqual(parametros.ejercicio, 2026)


# --------------------------------------------------
class TestAddManyOtrosGastos(unittest.IsolatedAsyncioTestCase):
    """add_many congela el snapshot con borrado idempotente por ejercicio."""

    # --------------------------------------------------
    async def test_add_many_siif_borra_por_ejercicio(self) -> None:
        repositorio = RepositorioFalso()
        servicio = construir_servicio_siif(
            GastosFalso([]), repository=repositorio
        )

        resultado = await servicio.add_many([fila_siif("00001/05", "00001")])

        self.assertEqual(repositorio.deleted_filters, [{"ejercicio": 2026}])
        self.assertFalse(repositorio.deleted_all_llamado)
        self.assertEqual(len(repositorio.saved), 1)
        self.assertEqual(resultado.added, 1)

    # --------------------------------------------------
    async def test_add_many_sgf_borra_por_ejercicio(self) -> None:
        repositorio = RepositorioFalso()
        servicio = ControlOtrosGastosSgfService(
            repository=repositorio,
            resumen_rend_service=ResumenRendFalso([]),
            cta_cte_service=CtaCteFalso(),
        )

        resultado = await servicio.add_many([fila_sgf("L-1")])

        self.assertEqual(repositorio.deleted_filters, [{"ejercicio": 2026}])
        self.assertFalse(repositorio.deleted_all_llamado)
        self.assertEqual(len(repositorio.saved), 1)
        self.assertEqual(resultado.added, 1)

    # --------------------------------------------------
    async def test_add_many_siif_sin_validos_lanza_400(self) -> None:
        servicio = construir_servicio_siif(GastosFalso([]))
        with self.assertRaises(HTTPException) as contexto:
            await servicio.add_many([{"nro_comprobante": "incompleto"}])
        self.assertEqual(contexto.exception.status_code, 400)


# --------------------------------------------------
class TestRutasOtrosGastos(unittest.TestCase):
    """Superficie: 2 conjuntos de rutas + 1 export unificado."""

    # --------------------------------------------------
    def test_conjunto_siif(self) -> None:
        rutas = {ruta.path for ruta in control_otros_gastos_siif_router.routes}
        self.assertIn("/otrosGastos/siif", rutas)  # Get All / Add / Delete
        self.assertIn("/otrosGastos/siif/generate", rutas)
        # El export por lado NO existe: es unificado
        self.assertNotIn("/otrosGastos/siif/export", rutas)

    # --------------------------------------------------
    def test_conjunto_sgf(self) -> None:
        rutas = {ruta.path for ruta in control_otros_gastos_sgf_router.routes}
        self.assertIn("/otrosGastos/sgf", rutas)
        self.assertIn("/otrosGastos/sgf/generate", rutas)
        self.assertNotIn("/otrosGastos/sgf/export", rutas)

    # --------------------------------------------------
    def test_export_unificado_unico(self) -> None:
        rutas = {ruta.path for ruta in control_otros_gastos_router.routes}
        self.assertEqual(rutas, {"/otrosGastos/export"})


# --------------------------------------------------
class TestExportOtrosGastos(unittest.IsolatedAsyncioTestCase):
    """Export unificado: 1 ruta → 1 Google Sheet con 2 hojas."""

    # --------------------------------------------------
    async def test_export_sin_key_lanza_400(self) -> None:
        """Con la key vacía la ruta responde 400 explícito."""
        servicio = ControlOtrosGastosExportService(
            siif_service=SimpleNamespace(),
            sgf_service=SimpleNamespace(),
        )
        with mock.patch(
            "src.analysis.services.control_otros_gastos."
            "SPREADSHEET_KEY_CONTROL_OTROS_GASTOS",
            "",
        ):
            with self.assertRaises(HTTPException) as contexto:
                await servicio.export(
                    ControlOtrosGastosExportFilter(ejercicio=2026)
                )
        self.assertEqual(contexto.exception.status_code, 400)

    # --------------------------------------------------
    async def test_export_sube_2_hojas_al_mismo_key(self) -> None:
        """Las 2 tablas (snapshot) suben al MISMO Google Sheet."""
        servicio = ControlOtrosGastosExportService(
            siif_service=SimpleNamespace(
                get_all=mock.AsyncMock(
                    return_value=[
                        ControlOtrosGastosSiifReport(**fila_siif("00001/05", "00001"))
                    ]
                ),
                compute_otros_gastos_siif=mock.AsyncMock(return_value=[]),
            ),
            sgf_service=SimpleNamespace(
                get_all=mock.AsyncMock(
                    return_value=[ControlOtrosGastosSgfReport(**fila_sgf("L-1"))]
                ),
                compute_otros_gastos_sgf=mock.AsyncMock(return_value=[]),
            ),
        )

        with mock.patch(
            "src.analysis.services.control_otros_gastos."
            "SPREADSHEET_KEY_CONTROL_OTROS_GASTOS",
            "clave-del-sheet",
        ), mock.patch(
            "src.analysis.services.control_otros_gastos."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            await servicio._export_to_google_sheets(
                ControlOtrosGastosExportFilter(ejercicio=2026)
            )

        upload_mock.assert_called_once()
        sheets = upload_mock.call_args.args[0]
        self.assertEqual(
            [nombre for _, nombre in sheets], [HOJA_SIIF, HOJA_SGF]
        )
        self.assertEqual(
            upload_mock.call_args.kwargs["spreadsheet_key"], "clave-del-sheet"
        )

    # --------------------------------------------------
    async def test_export_falla_a_compute_si_snapshot_vacio(self) -> None:
        """Sin snapshot cae al cómputo on-demand de cada lado."""
        servicio = ControlOtrosGastosExportService(
            siif_service=SimpleNamespace(
                get_all=mock.AsyncMock(return_value=[]),
                compute_otros_gastos_siif=mock.AsyncMock(
                    return_value=[fila_siif("00001/05", "00001")]
                ),
            ),
            sgf_service=SimpleNamespace(
                get_all=mock.AsyncMock(return_value=[]),
                compute_otros_gastos_sgf=mock.AsyncMock(
                    return_value=[fila_sgf("L-1")]
                ),
            ),
        )

        with mock.patch(
            "src.analysis.services.control_otros_gastos."
            "SPREADSHEET_KEY_CONTROL_OTROS_GASTOS",
            "clave-del-sheet",
        ), mock.patch(
            "src.analysis.services.control_otros_gastos."
            "upload_multiple_dataframes_to_google_sheets"
        ) as upload_mock:
            await servicio._export_to_google_sheets(
                ControlOtrosGastosExportFilter(ejercicio=2026)
            )

        upload_mock.assert_called_once()
        sheets = upload_mock.call_args.args[0]
        self.assertEqual(
            [nombre for _, nombre in sheets], [HOJA_SIIF, HOJA_SGF]
        )


# --------------------------------------------------
if __name__ == "__main__":
    unittest.main()




