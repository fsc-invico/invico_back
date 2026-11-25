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
  y subida de las 4 hojas al MISMO key (snapshot + fallback).
- ``compute_cruce`` (Capa 1 pareo 1:1 + Capa 2 mensual de fondos
  permanentes), ``add_many``/``delete_many``/``get_snapshot`` sobre las
  2 colecciones del cruce y la superficie de rutas ``/otrosGastos/cruce``.

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
    control_otros_gastos_cruce_router,
    control_otros_gastos_router,
    control_otros_gastos_sgf_router,
    control_otros_gastos_siif_router,
)
from src.analysis.schemas import (
    ESTADO_PAREADO,
    ESTADO_SGF_SIN_SIIF,
    ESTADO_SIIF_SIN_SGF,
    ControlOtrosGastosCruceFilter,
    ControlOtrosGastosCruceGenerateFilter,
    ControlOtrosGastosCruceLiteFilter,
    ControlOtrosGastosCruceReport,
    ControlOtrosGastosCruceSnapshot,
    ControlOtrosGastosExportFilter,
    ControlOtrosGastosGenerateFilter,
    ControlOtrosGastosSgfFilter,
    ControlOtrosGastosSgfReport,
    ControlOtrosGastosSiifFilter,
    ControlOtrosGastosSiifReport,
)
from src.analysis.services import (
    ControlOtrosGastosCruceService,
    ControlOtrosGastosExportService,
    ControlOtrosGastosSgfService,
    ControlOtrosGastosSiifService,
)
from src.analysis.services.control_otros_gastos import (
    HOJA_CRUCE_FONDOS_PERM,
    HOJA_CRUCE_RESTO,
    HOJA_SGF,
    HOJA_SIIF,
)
from src.config import logger as logger_pruebas


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio en memoria que registra las operaciones de add_many."""

    def __init__(
        self, filas_previas: int = 4, documentos: Optional[List[Any]] = None
    ) -> None:
        self.filas_previas = filas_previas
        self.deleted_filters: List[dict] = []
        self.deleted_all_llamado = False
        self.saved: List[Any] = []
        self.documentos: List[Any] = documentos or []

    # --------------------------------------------------
    async def find_with_filter_params(self, params: Any) -> List[Any]:
        return list(self.documentos)

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
    fecha: str = "01/05/2026",
    mes: str = "05/2026",
    importe: float = 100.0,
) -> dict:
    return {
        "ejercicio": 2026,
        "mes": mes,
        "fecha": fecha,
        "nro_comprobante": nro_comprobante,
        "importe": importe,
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
    cuit: str = "20223334445",
    fecha: str = "01/05/2026",
    mes: str = "05/2026",
    importe: float = 100.0,
) -> dict:
    return {
        "origen": origen,
        "ejercicio": 2026,
        "mes": mes,
        "fecha": fecha,
        "beneficiario": "PROVEEDOR SA",
        "destino": destino,
        "libramiento": libramiento,
        "movimiento": "CHEQUE",
        "cta_cte": cta_cte,
        "importe_bruto": importe,
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
        "importe_neto": importe,
        "cuit": cuit,
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
        """Cada paso descuenta su conjunto; quedan la fila 'ok' y la
        caja chica (que ya NO se depura: se cruza 1:1 con SGF)."""
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
            fila_siif(  # caja chica (REG + fondo + cuit ≠ INVICO): se queda
                "00011/05", "00011", nro_fondo="77"
            ),
        ]
        servicio = construir_servicio_siif(GastosFalso(base))

        resultado = await servicio.compute_otros_gastos_siif(
            params=ControlOtrosGastosSiifFilter(ejercicio=2026, limit=None)
        )

        nros = [fila["nro_comprobante"] for fila in resultado]
        self.assertEqual(nros, ["00001/05", "00011/05"])

    # --------------------------------------------------
    async def test_depuracion_fondos_pa6(self) -> None:
        """Solo los REG cuyo nro_fondo es de un PA6 del ejercicio salen."""
        base = [
            fila_siif("00020/05", "00020", nro_fondo="97"),  # fondo PA6
            fila_siif(  # otro fondo (cuit INVICO: fondos permanentes);
                #              42 no está en PA6 → aisla el paso 4)
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
    async def test_cajas_chicas_no_se_depuran(self) -> None:
        """Las cajas chicas se conservan: SÍ están en SGF y se cruzan
        uno a uno en la Capa 1 (criterio corregido; antes se removían)."""
        base = [
            fila_siif(  # caja chica: REG + fondo + cuit ≠ INVICO → queda
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
            nros, ["00040/05", "00041/05", "00042/05", "00043/05", "00044/05"]
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
    async def test_add_many_siif_con_descartes_registra_warning(self) -> None:
        """Si la validación descarta filas, el servicio avisa en logs.

        Sin este warning, un snapshot parcial pasa inadvertido (fue lo
        que dejó la hoja SIIF sin el resto de registros)."""
        repositorio = RepositorioFalso()
        servicio = construir_servicio_siif(
            GastosFalso([]), repository=repositorio
        )
        payload: List[Any] = [
            fila_siif("00001/05", "00001"),
            {"nro_comprobante": "incompleto"},  # falla validación
        ]

        with self.assertLogs(logger_pruebas, level="WARNING") as capturado:
            resultado = await servicio.add_many(payload)  # type: ignore[arg-type]

        self.assertEqual(resultado.added, 1)
        self.assertTrue(
            any("1 de 2 filas descartadas" in m for m in capturado.output)
        )


# --------------------------------------------------
class TestEsquemaToleranteANan(unittest.IsolatedAsyncioTestCase):
    """El frontend arma los payloads pasando las filas por un
    ``pd.DataFrame``: los opcionales ausentes llegan como ``NaN``
    (httpx serializa con ``allow_nan=True``). Sin la coerción de los
    esquemas, Pydantic rechaza ``nan`` en campos ``str`` y ``add_many``
    descarta filas COMPLETAS en silencio: fue lo que dejó la hoja
    ``otros_gastos_siif`` sin el resto (``nro_fondo`` nulo) y la SGF
    sin los cuit nulos, vaciando el cruce 1:1."""

    # --------------------------------------------------
    def test_siif_nan_en_opcional_queda_none(self) -> None:
        """El nro_fondo nulo (np.nan del DataFrame) valida como None."""
        fila = ControlOtrosGastosSiifReport(
            **fila_siif(  # type: ignore[arg-type]
                "00048/26", "00048", nro_fondo=float("nan")
            )
        )
        self.assertIsNone(fila.nro_fondo)

    # --------------------------------------------------
    def test_siif_numericos_coaccionan_a_texto(self) -> None:
        """Enteros y floats enteros llegan como texto normalizado."""
        fila = ControlOtrosGastosSiifReport(
            **fila_siif(  # type: ignore[arg-type]
                "00048/26",
                "00048",
                nro_expte=900008022026,  # type: ignore[arg-type]
                nro_fondo=27.0,  # type: ignore[arg-type]
                grupo=3.0,  # type: ignore[arg-type]
                partida=333,  # type: ignore[arg-type]
            )
        )
        self.assertEqual(fila.nro_expte, "900008022026")
        self.assertEqual(fila.nro_fondo, "27")
        self.assertEqual(fila.grupo, "3")
        self.assertEqual(fila.partida, "333")

    # --------------------------------------------------
    def test_sgf_cuit_nan_queda_none(self) -> None:
        """Los cuit nulos del SGF deben validar (antes se caían)."""
        fila = ControlOtrosGastosSgfReport(
            **fila_sgf("L-9", cuit=float("nan"))  # type: ignore[arg-type]
        )
        self.assertIsNone(fila.cuit)

    # --------------------------------------------------
    async def test_add_many_siif_persiste_filas_con_opcionales_nulos(
        self,
    ) -> None:
        """Una fila tipo 'resto' con opcionales nulos sobrevive al POST."""
        repositorio = RepositorioFalso()
        servicio = construir_servicio_siif(
            GastosFalso([]), repository=repositorio
        )
        resto = fila_siif(
            "00048/26", "00048", clase_reg="CYO", nro_fondo=float("nan")  # type: ignore[arg-type]
        )

        resultado = await servicio.add_many([resto])  # type: ignore[arg-type]

        self.assertEqual(resultado.added, 1)
        self.assertEqual(len(repositorio.saved), 1)


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
    def test_conjunto_cruce(self) -> None:
        """Cruce: snapshot (GET/POST/DELETE) + /generate, sin export."""
        rutas = {ruta.path for ruta in control_otros_gastos_cruce_router.routes}
        self.assertEqual(
            rutas, {"/otrosGastos/cruce", "/otrosGastos/cruce/generate"}
        )

    # --------------------------------------------------
    def test_export_unificado_unico(self) -> None:
        rutas = {ruta.path for ruta in control_otros_gastos_router.routes}
        self.assertEqual(rutas, {"/otrosGastos/export"})


# --------------------------------------------------
def _cruce_falso(
    pareos: Optional[List[dict]] = None,
    mensual: Optional[List[dict]] = None,
) -> SimpleNamespace:
    """Servicio de cruce simulado para el export (snapshot + generate)."""
    bloque = {
        "ejercicio": 2026,
        "pareos": pareos if pareos is not None else [],
        "mensual": mensual if mensual is not None else [],
    }
    return SimpleNamespace(
        get_snapshot=mock.AsyncMock(return_value=bloque),
        generate=mock.AsyncMock(return_value=bloque),
    )


# --------------------------------------------------
class TestExportOtrosGastos(unittest.IsolatedAsyncioTestCase):
    """Export unificado: 1 ruta → 1 Google Sheet con 4 hojas."""

    # --------------------------------------------------
    async def test_export_sin_key_lanza_400(self) -> None:
        """Con la key vacía la ruta responde 400 explícito."""
        servicio = ControlOtrosGastosExportService(
            siif_service=SimpleNamespace(),
            sgf_service=SimpleNamespace(),
            cruce_service=_cruce_falso(),
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
    async def test_export_sube_4_hojas_al_mismo_key(self) -> None:
        """Las 4 tablas (2 depuradas + 2 del cruce) suben al MISMO Sheet."""
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
            cruce_service=_cruce_falso(
                pareos=[{"ejercicio": 2026, "estado": ESTADO_PAREADO}],
                mensual=[{"ejercicio": 2026, "mes": "05/2026"}],
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
            [nombre for _, nombre in sheets],
            [HOJA_SIIF, HOJA_SGF, HOJA_CRUCE_RESTO, HOJA_CRUCE_FONDOS_PERM],
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
            cruce_service=SimpleNamespace(
                # snapshot vacío → el export debe caer al /generate
                get_snapshot=mock.AsyncMock(
                    return_value={"ejercicio": 2026, "pareos": [], "mensual": []}
                ),
                generate=mock.AsyncMock(
                    return_value={
                        "ejercicio": 2026,
                        "pareos": [
                            {"ejercicio": 2026, "estado": ESTADO_PAREADO}
                        ],
                        "mensual": [{"ejercicio": 2026, "mes": "05/2026"}],
                    }
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
        # Snapshot del cruce vacío → fallback al /generate
        servicio.cruce_service.generate.assert_awaited_once()
        sheets = upload_mock.call_args.args[0]
        self.assertEqual(
            [nombre for _, nombre in sheets],
            [HOJA_SIIF, HOJA_SGF, HOJA_CRUCE_RESTO, HOJA_CRUCE_FONDOS_PERM],
        )


# --------------------------------------------------
class SiifDepuradoFalso:
    """Snapshot vacío; devuelve las filas del cómputo SIIF simulado."""

    def __init__(self, filas: List[dict]) -> None:
        self.filas = filas

    # --------------------------------------------------
    async def get_all(self, params: Any) -> List[Any]:
        return []

    # --------------------------------------------------
    async def compute_otros_gastos_siif(self, params: Any) -> List[dict]:
        return self.filas


# --------------------------------------------------
class SgfDepuradoFalso:
    """Snapshot vacío; devuelve las filas del cómputo SGF simulado."""

    def __init__(self, filas: List[dict]) -> None:
        self.filas = filas

    # --------------------------------------------------
    async def get_all(self, params: Any) -> List[Any]:
        return []

    # --------------------------------------------------
    async def compute_otros_gastos_sgf(self, params: Any) -> List[dict]:
        return self.filas


# --------------------------------------------------
def construir_servicio_cruce(
    siif_filas: List[dict],
    sgf_filas: List[dict],
    repositorio: Optional[RepositorioFalso] = None,
    repositorio_mensual: Optional[RepositorioFalso] = None,
) -> ControlOtrosGastosCruceService:
    """Instancia el servicio de cruce con dependencias simuladas."""
    return ControlOtrosGastosCruceService(
        cruce_repository=repositorio or RepositorioFalso(),
        cruce_mensual_repository=repositorio_mensual or RepositorioFalso(),
        siif_service=SiifDepuradoFalso(siif_filas),
        sgf_service=SgfDepuradoFalso(sgf_filas),
    )


# --------------------------------------------------
class TestCruceOtrosGastos(unittest.IsolatedAsyncioTestCase):
    """compute_cruce: Capa 1 (pareo 1:1) + Capa 2 (mensual)."""

    # --------------------------------------------------
    async def test_cruce_dos_capas(self) -> None:
        """Pareo, huérfanos de ambos lados y mensual de fondos perm."""
        siif_filas = [
            fila_siif(
                "00001/05", "00001", cuit="20111111111", importe=1000.0
            ),
            fila_siif(
                "00002/05", "00002", cuit="20222222222", importe=2000.0
            ),
            fila_siif(  # fondo permanente: REG + cuit INVICO
                "00003/05", "00003", cuit="30632351514", importe=5000.0
            ),
        ]
        sgf_filas = [
            fila_sgf("L-1", cuit="20111111111", importe=1000.0),  # pareo
            fila_sgf("L-2", cuit="20222222222", importe=3000.0),  # huérfana
            fila_sgf("L-3", cuit="20333333333", importe=4500.0),  # con fondo
        ]
        servicio = construir_servicio_cruce(siif_filas, sgf_filas)

        bloque = await servicio.compute_cruce(
            params=ControlOtrosGastosCruceFilter(ejercicio=2026, limit=None)
        )

        estados = [fila["estado"] for fila in bloque["pareos"]]
        self.assertEqual(
            estados,
            [ESTADO_PAREADO, ESTADO_SIIF_SIN_SGF, ESTADO_SGF_SIN_SIIF],
        )

        pareado = bloque["pareos"][0]
        self.assertEqual(pareado["siif_nro_comprobante"], "00001/05")
        self.assertEqual(pareado["sgf_libramiento"], "L-1")
        self.assertEqual(pareado["dias_dif"], 0)
        self.assertEqual(pareado["dif"], 0.0)

        sin_sgf = bloque["pareos"][1]
        self.assertEqual(sin_sgf["siif_nro_comprobante"], "00002/05")
        self.assertIsNone(sin_sgf["sgf_libramiento"])

        huerfana = bloque["pareos"][2]
        self.assertEqual(huerfana["sgf_libramiento"], "L-2")
        self.assertIsNone(huerfana["siif_nro_comprobante"])

        # Capa 2: solo el fondo permanente de SIIF y el SGF fuera del
        # dominio del resto (L-3) forman el mensual.
        self.assertEqual(len(bloque["mensual"]), 1)
        mensual = bloque["mensual"][0]
        self.assertEqual(mensual["mes"], "05/2026")
        self.assertEqual(mensual["siif_rendido"], 5000.0)
        self.assertEqual(mensual["sgf_pagado"], 4500.0)
        self.assertEqual(mensual["dif_mes"], 500.0)
        self.assertEqual(mensual["siif_acum"], 5000.0)
        self.assertEqual(mensual["sgf_acum"], 4500.0)
        self.assertEqual(mensual["dif_acum"], 500.0)
        self.assertAlmostEqual(mensual["dif_pct"], 100 * 500 / 4500)


    # --------------------------------------------------
    async def test_cruce_tolerancia_importe(self) -> None:
        """Fuera de tolerancia → sin pareo; con tolerancia → parea."""
        siif_filas = [
            fila_siif(
                "00010/05", "00010", cuit="20111111111", importe=1000.0
            )
        ]
        sgf_filas = [
            # 0.6% de diferencia > 0.5% por defecto
            fila_sgf("L-10", cuit="20111111111", importe=1006.0)
        ]
        servicio = construir_servicio_cruce(siif_filas, sgf_filas)
        params = ControlOtrosGastosCruceFilter(ejercicio=2026, limit=None)

        bloque = await servicio.compute_cruce(params=params)
        estados = [fila["estado"] for fila in bloque["pareos"]]
        self.assertEqual(estados, [ESTADO_SIIF_SIN_SGF, ESTADO_SGF_SIN_SIIF])

        bloque = await servicio.compute_cruce(params=params, importe_tol=0.01)
        estados = [fila["estado"] for fila in bloque["pareos"]]
        self.assertEqual(estados, [ESTADO_PAREADO])

    # --------------------------------------------------
    async def test_cruce_ventana_fecha(self) -> None:
        """Fuera de la ventana → sin pareo; ampliando la ventana → parea."""
        siif_filas = [
            fila_siif(
                "00020/05",
                "00020",
                cuit="20111111111",
                importe=1000.0,
                fecha="01/05/2026",
            )
        ]
        sgf_filas = [
            fila_sgf(
                "L-20",
                cuit="20111111111",
                importe=1000.0,
                fecha="20/06/2026",
            )
        ]  # 50 días
        servicio = construir_servicio_cruce(siif_filas, sgf_filas)
        params = ControlOtrosGastosCruceFilter(ejercicio=2026, limit=None)

        bloque = await servicio.compute_cruce(params=params)
        estados = [fila["estado"] for fila in bloque["pareos"]]
        self.assertEqual(estados, [ESTADO_SIIF_SIN_SGF, ESTADO_SGF_SIN_SIIF])

        bloque = await servicio.compute_cruce(params=params, ventana_dias=60)
        estados = [fila["estado"] for fila in bloque["pareos"]]
        self.assertEqual(estados, [ESTADO_PAREADO])

    # --------------------------------------------------
    async def test_generate_delega_en_compute(self) -> None:
        """generate llama a compute con ejercicio y tolerancias."""
        servicio = construir_servicio_cruce([], [])
        bloque_esperado = {"ejercicio": 2026, "pareos": [], "mensual": []}

        with mock.patch.object(
            servicio,
            "compute_cruce",
            new=mock.AsyncMock(return_value=bloque_esperado),
        ) as compute_mock:
            resultado = await servicio.generate(
                ControlOtrosGastosCruceGenerateFilter(
                    ejercicio=2026, importe_tol=0.01, ventana_dias=60
                )
            )

        self.assertEqual(resultado, bloque_esperado)
        compute_mock.assert_awaited_once()
        self.assertEqual(compute_mock.await_args.kwargs["importe_tol"], 0.01)
        self.assertEqual(compute_mock.await_args.kwargs["ventana_dias"], 60)


# --------------------------------------------------
class TestSnapshotCruce(unittest.IsolatedAsyncioTestCase):
    """add_many/delete_many/get_snapshot sobre AMBAS colecciones."""

    # --------------------------------------------------
    async def test_add_many_persiste_ambas_colecciones(self) -> None:
        repositorio = RepositorioFalso()
        repositorio_mensual = RepositorioFalso()
        servicio = construir_servicio_cruce(
            [],
            [],
            repositorio=repositorio,
            repositorio_mensual=repositorio_mensual,
        )
        snapshot = ControlOtrosGastosCruceSnapshot(
            ejercicio=2026,
            pareos=[
                {
                    "ejercicio": 2026,
                    "estado": ESTADO_PAREADO,
                    "siif_nro_comprobante": "00001/05",
                }
            ],
            mensual=[
                {
                    "ejercicio": 2026,
                    "mes": "05/2026",
                    "siif_rendido": 1.0,
                    "sgf_pagado": 1.0,
                    "dif_mes": 0.0,
                    "siif_acum": 1.0,
                    "sgf_acum": 1.0,
                    "dif_acum": 0.0,
                    "dif_pct": 0.0,
                }
            ],
        )

        resultado = await servicio.add_many(snapshot)

        self.assertEqual(repositorio.deleted_filters, [{"ejercicio": 2026}])
        self.assertEqual(
            repositorio_mensual.deleted_filters, [{"ejercicio": 2026}]
        )
        self.assertEqual(len(repositorio.saved), 1)
        self.assertEqual(len(repositorio_mensual.saved), 1)
        self.assertEqual(resultado.added, 2)

    # --------------------------------------------------
    async def test_add_many_vacio_lanza_400(self) -> None:
        servicio = construir_servicio_cruce([], [])
        with self.assertRaises(HTTPException) as contexto:
            await servicio.add_many(
                ControlOtrosGastosCruceSnapshot(ejercicio=2026)
            )
        self.assertEqual(contexto.exception.status_code, 400)

    # --------------------------------------------------
    async def test_delete_many_borra_ambas_colecciones(self) -> None:
        repositorio = RepositorioFalso(filas_previas=3)
        repositorio_mensual = RepositorioFalso(filas_previas=2)
        servicio = construir_servicio_cruce(
            [],
            [],
            repositorio=repositorio,
            repositorio_mensual=repositorio_mensual,
        )

        resultado = await servicio.delete_many(
            ControlOtrosGastosCruceLiteFilter(ejercicio=2026)
        )

        self.assertEqual(repositorio.deleted_filters, [{"ejercicio": 2026}])
        self.assertEqual(
            repositorio_mensual.deleted_filters, [{"ejercicio": 2026}]
        )
        self.assertEqual(resultado["deleted"], 5)

    # --------------------------------------------------
    async def test_get_snapshot_lee_ambas_colecciones(self) -> None:
        documento = ControlOtrosGastosCruceReport(
            ejercicio=2026,
            estado=ESTADO_PAREADO,
            siif_nro_comprobante="00001/05",
        )
        repositorio = RepositorioFalso(documentos=[documento])
        repositorio_mensual = RepositorioFalso()
        servicio = construir_servicio_cruce(
            [],
            [],
            repositorio=repositorio,
            repositorio_mensual=repositorio_mensual,
        )

        bloque = await servicio.get_snapshot(
            ControlOtrosGastosCruceFilter(ejercicio=2026, limit=None)
        )

        self.assertEqual(bloque["ejercicio"], 2026)
        self.assertEqual(len(bloque["pareos"]), 1)
        self.assertEqual(bloque["pareos"][0]["estado"], ESTADO_PAREADO)
        self.assertEqual(bloque["mensual"], [])


# --------------------------------------------------
if __name__ == "__main__":
    unittest.main()




