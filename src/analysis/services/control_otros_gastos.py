__all__ = [
    "ControlOtrosGastosSiifService",
    "ControlOtrosGastosSiifServiceDependency",
    "ControlOtrosGastosSgfService",
    "ControlOtrosGastosSgfServiceDependency",
    "ControlOtrosGastosExportService",
    "ControlOtrosGastosExportServiceDependency",
]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from ...config import logger
from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...siif.schemas import GtoRpa03gFullFilter, Rcg01UejpFullFilter
from ...siif.services import GtoRpa03gServiceDependency, Rcg01UejpServiceDependency
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories import (
    ControlOtrosGastosSgfRepositoryDependency,
    ControlOtrosGastosSiifRepositoryDependency,
)
from ..schemas import (
    ControlHonorariosFullFilter,
    ControlOtrosGastosExportFilter,
    ControlOtrosGastosGenerateFilter,
    ControlOtrosGastosSgfDocument,
    ControlOtrosGastosSgfFilter,
    ControlOtrosGastosSgfLiteFilter,
    ControlOtrosGastosSgfReport,
    ControlOtrosGastosSiifDocument,
    ControlOtrosGastosSiifFilter,
    ControlOtrosGastosSiifLiteFilter,
    ControlOtrosGastosSiifReport,
)
from .control_debitos_bancarios import ControlDebitosBancariosServiceDependency
from .control_escribanos import CTA_CTE_ESCRIBANOS
from .control_honorarios import ControlHonorariosServiceDependency
from .control_viaticos import ControlViaticosServiceDependency

# CUIT de INVICO (beneficiario de los comprobantes de honorarios)
CUIT_INVICO: str = "30632351514"

# Partidas excluidas de haberes por control_haberes (aportes 150/151)
PARTIDAS_HABERES_EXCLUIDAS: List[str] = ["150", "151"]

# Key del Google Sheet destino del export unificado:
# https://docs.google.com/spreadsheets/d/1EBzBz17mtVzBmpAFznDyJf2RAJNspQyJQJaRD_WI5dE
# GET /control/otrosGastos/export sube acá las 2 hojas (SIIF y SGF).
# Si algún día se vacía, la ruta responde 400 con mensaje explícito
# (sin fallos silenciosos).
SPREADSHEET_KEY_CONTROL_OTROS_GASTOS: str = (
    "1EBzBz17mtVzBmpAFznDyJf2RAJNspQyJQJaRD_WI5dE"
)

# Hojas del Google Sheet unificado (una por sistema depurado).
HOJA_SIIF: str = "otros_gastos_siif"
HOJA_SGF: str = "otros_gastos_sgf"

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()

# Icaro: tipos de comprobante que controla control_obras y que por lo
# tanto hay que depurar de SIIF por nro_comprobante. PA6 (subsistema de
# fondos) queda FUERA: no representa gasto de rcg01_uejp.
TIPOS_ICARO_OBRAS: List[str] = ["REG", "CYO"]

# Espejo de get_sgf_honorarios (control_honorarios): destinos y cuentas
# corrientes de honorarios que ya cubre ese control.
DESTINOS_HONORARIOS_SGF: List[str] = [
    "HONORARIOS - FUNCIONAMIENTO",
    "COMISIONES - FUNCIONAMIENTO",
    "HONORARIOS - EPAM",
]
CTAS_HONORARIOS_SGF: List[str] = ["130832-05", "130832-07"]

# Orden de columnas de cada tabla de detalle (solo se conservan las que
# existan en el DataFrame).
COLUMNAS_SIIF: List[str] = [
    "ejercicio",
    "mes",
    "fecha",
    "nro_comprobante",
    "importe",
    "fuente",
    "cta_cte",
    "cuit",
    "beneficiario",
    "nro_expte",
    "nro_fondo",
    "nro_entrada",
    "nro_origen",
    "grupo",
    "partida",
    "glosa",
    "clase_reg",
    "clase_mod",
    "clase_gto",
    "es_comprometido",
    "es_verificado",
    "es_aprobado",
    "es_pagado",
]
COLUMNAS_SGF: List[str] = [
    "origen",
    "ejercicio",
    "mes",
    "fecha",
    "beneficiario",
    "destino",
    "libramiento",
    "movimiento",
    "cta_cte",
    "cuit",
    "importe_bruto",
    "gcias",
    "sellos",
    "iibb",
    "suss",
    "invico",
    "seguro",
    "salud",
    "mutual",
    "otras",
    "retenciones",
    "importe_neto",
]

@dataclass
# -------------------------------------------------
class ControlOtrosGastosSiifService(
    BaseService[
        ControlOtrosGastosSiifReport,
        ControlOtrosGastosSiifDocument,
        ControlOtrosGastosSiifFilter,
        ControlOtrosGastosSiifLiteFilter,
    ]
):
    """Tabla SIIF depurada: gto_rpa03g unido con rcg01_uejp con todo lo
    que ya cubren los demás controles removido (ver
    :meth:`compute_otros_gastos_siif`)."""

    repository: ControlOtrosGastosSiifRepositoryDependency
    gastos_service: GtoRpa03gServiceDependency
    rcg01_service: Rcg01UejpServiceDependency
    icaro_carga_service: CargaServiceDependency
    honorarios_service: ControlHonorariosServiceDependency
    viaticos_service: ControlViaticosServiceDependency
    debitos_service: ControlDebitosBancariosServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base:
        # de ahí salen get_all (Get All / snapshot) y delete_many
        # (Delete) que registra el GenericRouterFactory.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlOtrosGastosSiifFilter,
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[ControlOtrosGastosSiifReport]
    ) -> RouteReturnSchema:
        """Persiste la tabla depurada con borrado idempotente por
        ejercicio (contraparte del GET /siif/generate)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlOtrosGastosSiifReport,
                field_id=["ejercicio", "nro_comprobante", "partida"],
            )

            if not validation_result.validated:
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    detalle = validation_result.errors[:2]
                    detail_msg += f" Errores detectados: {detalle}"
                raise HTTPException(status_code=400, detail=detail_msg)

            ejercicio_detectado = validation_result.validated[0].ejercicio
            delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Otros Gastos SIIF",
                label="Otros Gastos SIIF",
                logger=logger,
            )

        except HTTPException:
            # Respeta el 400 de "sin registros válidos" (no lo envuelve en 500)
            raise
        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self, params: ControlOtrosGastosGenerateFilter
    ) -> List[ControlOtrosGastosSiifReport]:
        """Tabla SIIF depurada on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Filas de detalle validadas como
            ``ControlOtrosGastosSiifReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlOtrosGastosSiifFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_otros_gastos_siif(params=compute_params)

    # -------------------------------------------------
    async def export(
        self, params: ControlOtrosGastosSiifLiteFilter
    ) -> StreamingResponse:
        """El export es UNIFICADO: las 2 tablas (SIIF y SGF) suben a un
        único Google Sheet desde GET /control/otrosGastos/export.

        Esta implementación existe solo por el contrato abstracto de
        ``BaseService``: la ruta /export automática del
        GenericRouterFactory se elimina del router.
        """
        raise HTTPException(
            status_code=400,
            detail=(
                "El export de Otros Gastos es unificado: use "
                "GET /control/otrosGastos/export (una sola ruta, un "
                "único Google Sheet con las hojas SIIF y SGF)."
            ),
        )

    # -------------------------------------------------
    async def compute_otros_gastos_siif(
        self, params: ControlOtrosGastosSiifFilter
    ) -> list[dict]:
        """Detalle fila a fila del SIIF depurado del ejercicio.

        Pasos de depuración (cada uno descuenta sobre el total y se
        loguea para poder medir el % restante):

        1. Base ``gto_rpa03g`` unido con ``rcg01_uejp``.
        2. Solo ``es_aprobado = True`` (las filas sin contraparte en
           rcg01 llegan con el flag nulo vía left join y también se
           descartan).
        3. Depura MAP: los ``clase_mod = "MAP"`` y el comprobante
           positivo que revierten (``MAP.nro_origen = fila.nro_entrada``).
        4. Obras: ``nro_comprobante`` de Icaro con ``tipo`` REG/CYO
           (PA6 no se usa: es subsistema de fondos).
        5. Haberes: cta. cte. 130832-04 sin las partidas 150/151
           (criterio de ``control_haberes``; se aplica sobre la cta_cte
           unificada porque el SIIF guarda "130832004" sin guiones).
        6. Honorarios: criterio de ``get_siif_honorarios`` (grupo 3,
           sin partida 384, cuit INVICO, ctas 130832-05/07 y glosa
           HONOR/RECON/LOC con cta_cte unificada) más el
           ``nro_comprobante`` de Slave de ``control_honorarios``.
        7. Viáticos: ``nro_comprobante``/``nro_expte`` de
           ``control_viaticos`` (partidas 372/373).
        8. Débitos bancarios: ``nro_comprobante`` de
           ``control_debitos_bancarios`` (partida 355).
        9. Escribanos NO se depura de SIIF (impactan como fondos, no
           como gastos).

        Args:
            params: Filtro con el ``ejercicio`` a depurar.

        Returns:
            Filas de detalle como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio: int = params.ejercicio
        etiqueta: str = f"Otros Gastos SIIF {ejercicio}"

        # 1. Base: gto_rpa03g ⟕ rcg01_uejp (trae partida/glosa y los
        #    campos de rcg01: clase_mod, es_aprobado, nro_entrada, etc.)
        gto_params = GtoRpa03gFullFilter(ejercicio=str(ejercicio), limit=None)
        data = await self.gastos_service.get_joined_with_rcg01_uejp(params=gto_params)
        df = pd.DataFrame(data) if data else pd.DataFrame()
        # importe_total es la proyección $temp_info.importe del join y
        # duplica importe; id es el _id interno de Mongo.
        df = df.drop(columns=["id", "importe_total"], errors="ignore")
        if df.empty:
            logger.info(f"{etiqueta}: sin datos de gto_rpa03g/rcg01_uejp.")
            return []
        total: int = len(df)
        logger.info(f"{etiqueta} → base gto⟕rcg01: {total} filas")

        # 1.b Unifica cta_cte con el nexo siif_gastos_cta_cte: el SIIF
        #     guarda "130832004" (sin guiones) y los criterios/controles
        #     usan el formato canónico "130832-04". Si no hay match se
        #     conserva el valor original (regla del unifier).
        df = await self.cta_cte_service.cta_cte_unifier(df, "siif_gastos_cta_cte")

        # 2. Solo aprobados
        df = df.loc[df["es_aprobado"].fillna(False).astype(bool)]
        logger.info(f"{etiqueta} → es_aprobado=True: {len(df)} filas")

        if df.empty:
            return []

        # 3. Depura MAP: los MAP y el comprobante positivo que revierten
        #    (MAP.nro_origen = nro_entrada del positivo).
        rcg_params = Rcg01UejpFullFilter(ejercicio=str(ejercicio), limit=None)
        rcg_params.set_extra_filter({"clase_mod": "MAP"})
        mapas = await self.rcg01_service.get_all(params=rcg_params)
        if mapas:
            nros_map = {m.nro_comprobante for m in mapas if m.nro_comprobante}
            nros_origen = {m.nro_origen for m in mapas if m.nro_origen}
            antes: int = len(df)
            df = df.loc[~(df["clase_mod"] == "MAP")]
            df = df.loc[~df["nro_comprobante"].isin(nros_map)]
            df = df.loc[~df["nro_entrada"].isin(nros_origen)]
            logger.info(f"{etiqueta} → MAP depurados: {antes - len(df)} filas")

        # 4. Obras: nro_comprobante de Icaro REG/CYO (sin PA6)
        carga_params = CargaFullFilter(ejercicio=str(ejercicio), limit=None)
        carga_params.set_extra_filter({"tipo": {"$in": TIPOS_ICARO_OBRAS}})
        carga_docs = await self.icaro_carga_service.get_all(params=carga_params)
        nros_obras = {
            doc.nro_comprobante for doc in carga_docs or [] if doc.nro_comprobante
        }
        if nros_obras:
            antes = len(df)
            df = df.loc[~df["nro_comprobante"].isin(nros_obras)]
            logger.info(f"{etiqueta} → obras (Icaro REG/CYO): {antes - len(df)}")

        # 5. Haberes: cta_cte 130832-04 sin las partidas 150/151
        #    (criterio INTENCIONAL de control_haberes, aplicado sobre la
        #    cta_cte ya unificada: ese control filtra la cta_cte CRUDA
        #    "130832-04" contra el valor sin guiones "130832004", por lo
        #    que su método no devuelve comprobantes del gto_rpa03g).
        antes = len(df)
        mask_haberes = (df["cta_cte"] == "130832-04") & ~df["partida"].isin(
            PARTIDAS_HABERES_EXCLUIDAS
        )
        df = df.loc[~mask_haberes]
        logger.info(f"{etiqueta} → haberes: {antes - len(df)} filas")

        if df.empty:
            return []

        # 6. Honorarios: criterio de get_siif_honorarios con cta_cte
        #    unificada (grupo 3, sin 384, cuit INVICO, ctas -05/-07 y
        #    glosa HONOR/RECON/LOC) ∪ nro_comprobante de Slave de
        #    control_honorarios (casi 10% de la ejecución del gasto).
        mask_honorarios = (
            (df["grupo"].astype(str) == "3")
            & (df["partida"] != "384")
            & (df["cuit"] == CUIT_INVICO)
            & df["cta_cte"].isin(CTAS_HONORARIOS_SGF)
            & df["glosa"].fillna("").str.contains("HONOR|RECON|LOC", case=False)
        )
        nros_honorarios = set(df.loc[mask_honorarios, "nro_comprobante"])
        hon_params = ControlHonorariosFullFilter(ejercicio=ejercicio, limit=None)
        try:
            slave_hon = await self.honorarios_service.get_slave_honorarios(
                params=hon_params
            )
        except HTTPException as exc:
            # Datos de Slave incompletos (p.ej. docs sin nombre_completo)
            # no deben tumbar toda la tabla: se sigue depurando con el
            # criterio SIIF y la incidencia queda logueada (visible en
            # consola / logs de Koyeb), nunca tragada en silencio.
            logger.warning(
                f"{etiqueta}: Slave honorarios no disponible "
                f"({exc.detail}); se depura solo con el criterio SIIF."
            )
            slave_hon = []
        nros_honorarios |= {
            fila.get("nro_comprobante")
            for fila in slave_hon or []
            if fila.get("nro_comprobante")
        }
        antes = len(df)
        df = df.loc[~df["nro_comprobante"].isin(nros_honorarios)]
        logger.info(f"{etiqueta} → honorarios: {antes - len(df)} filas")

        # 7. Viáticos: nro_comprobante y nro_expte de control_viaticos
        #    (partidas 372/373). Los PA3/REV de rfondos04 pertenecen al
        #    subsistema de fondos y no aparecen en gto_rpa03g: no se
        #    cruzan para evitar colisiones de numeración.
        viat_gastos = await self.viaticos_service.generate_siif_gastos(
            ejercicio=ejercicio
        )
        if viat_gastos is not None and not viat_gastos.empty:
            antes = len(df)
            if "nro_comprobante" in viat_gastos.columns:
                nros_viat = set(viat_gastos["nro_comprobante"].dropna())
                df = df.loc[~df["nro_comprobante"].isin(nros_viat)]
            if "nro_expte" in viat_gastos.columns:
                exptes = {
                    valor
                    for valor in viat_gastos["nro_expte"].dropna()
                    if str(valor).strip()
                }
                df = df.loc[~df["nro_expte"].isin(exptes)]
            logger.info(f"{etiqueta} → viáticos: {antes - len(df)} filas")

        # 8. Débitos bancarios: nro_comprobante de control_debitos_
        #    bancarios (partida 355).
        debitos = await self.debitos_service.generate_siif_debitos(ejercicio=ejercicio)
        if debitos is not None and not debitos.empty and (
            "nro_comprobante" in debitos.columns
        ):
            antes = len(df)
            nros_debitos = set(debitos["nro_comprobante"].dropna())
            df = df.loc[~df["nro_comprobante"].isin(nros_debitos)]
            logger.info(f"{etiqueta} → débitos bancarios: {antes - len(df)} filas")

        # 9. Escribanos NO se depura de SIIF (ver docstring).

        if df.empty:
            logger.info(f"{etiqueta}: sin registros después de depurar (0 de {total}).")
            return []

        # Selección de columnas, límite y sanitización final
        columnas = [col for col in COLUMNAS_SIIF if col in df.columns]
        df = df.loc[:, columnas]
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)
        logger.info(
            f"{etiqueta} → restantes: {len(df)} de {total} filas "
            f"({100 * len(df) / total:.1f}%)"
        )

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

@dataclass
# -------------------------------------------------
class ControlOtrosGastosSgfService(
    BaseService[
        ControlOtrosGastosSgfReport,
        ControlOtrosGastosSgfDocument,
        ControlOtrosGastosSgfFilter,
        ControlOtrosGastosSgfLiteFilter,
    ]
):
    """Tabla SGF depurada: resumen_rend_prov con todo lo que ya cubren
    los demás controles removido (ver
    :meth:`compute_otros_gastos_sgf`)."""

    repository: ControlOtrosGastosSgfRepositoryDependency
    resumen_rend_service: ResumenRendProvServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlOtrosGastosSgfFilter,
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[ControlOtrosGastosSgfReport]
    ) -> RouteReturnSchema:
        """Persiste la tabla depurada con borrado idempotente por
        ejercicio (contraparte del GET /sgf/generate)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlOtrosGastosSgfReport,
                field_id=["ejercicio", "origen", "libramiento"],
            )

            if not validation_result.validated:
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    detalle = validation_result.errors[:2]
                    detail_msg += f" Errores detectados: {detalle}"
                raise HTTPException(status_code=400, detail=detail_msg)

            ejercicio_detectado = validation_result.validated[0].ejercicio
            delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Otros Gastos SGF",
                label="Otros Gastos SGF",
                logger=logger,
            )

        except HTTPException:
            # Respeta el 400 de "sin registros válidos" (no lo envuelve en 500)
            raise
        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self, params: ControlOtrosGastosGenerateFilter
    ) -> List[ControlOtrosGastosSgfReport]:
        """Tabla SGF depurada on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Filas de detalle validadas como
            ``ControlOtrosGastosSgfReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlOtrosGastosSgfFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_otros_gastos_sgf(params=compute_params)

    # -------------------------------------------------
    async def export(
        self, params: ControlOtrosGastosSgfLiteFilter
    ) -> StreamingResponse:
        """El export es UNIFICADO: ver
        :meth:`ControlOtrosGastosSiifService.export`."""
        raise HTTPException(
            status_code=400,
            detail=(
                "El export de Otros Gastos es unificado: use "
                "GET /control/otrosGastos/export (una sola ruta, un "
                "único Google Sheet con las hojas SIIF y SGF)."
            ),
        )

    # -------------------------------------------------
    async def compute_otros_gastos_sgf(
        self, params: ControlOtrosGastosSgfFilter
    ) -> list[dict]:
        """Detalle fila a fila del SGF depurado del ejercicio.

        Parte de ``resumen_rend_prov`` ya desduplicado (mismo
        ``drop_duplicates_optimizado`` que usan los controles) y remueve
        lo que consumen los controles existentes:

        1. Obras: lo que consume ``control_obras`` (``unique_obras``:
           ``origen != FUNCIONAMIENTO`` sin los EPAM de honorarios).
        2. Honorarios: el filtro de ``get_sgf_honorarios``
           (``control_honorarios``).
        3. Escribanos: cta. cte. 130832-08 (``control_escribanos``).
        4. Haberes y viáticos no se depuran: SGF no los registra.

        Args:
            params: Filtro con el ``ejercicio`` a depurar.

        Returns:
            Filas de detalle como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
            HTTPException: 404 si no hay datos de SGF para el ejercicio.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio: int = params.ejercicio
        etiqueta: str = f"Otros Gastos SGF {ejercicio}"

        sgf_params = ResumenRendProvFullFilter(
            ejercicio=str(ejercicio),
            limit=None,
        )
        # Lanza 404 explícito si no hay crudos de SGF para el ejercicio
        # (no se traga el error en silencio).
        data = await self.resumen_rend_service.drop_duplicates_optimizado(
            params=sgf_params
        )
        if not data:
            return []
        df = pd.DataFrame(data)
        df = df.drop(columns=["id", "_id"], errors="ignore")
        if df.empty:
            return []
        total: int = len(df)
        logger.info(f"{etiqueta} → base deduplicada: {total} filas")

        # 1. Obras (control_obras = unique_obras): se remueve lo que
        #    consume ese control, es decir todo lo que NO es
        #    FUNCIONAMIENTO, salvo los EPAM de honorarios (que cubre
        #    control_honorarios).
        mask_obras = (df["origen"] != "FUNCIONAMIENTO") & ~(
            (df["origen"] == "EPAM")
            & df["destino"].str.contains("HONORARIOS", na=False)
        )

        # 2. Honorarios (control_honorarios = get_sgf_honorarios)
        mask_honorarios = (
            (df["origen"] != "OBRAS")
            & df["destino"].isin(DESTINOS_HONORARIOS_SGF)
            & df["cta_cte"].isin(CTAS_HONORARIOS_SGF)
        )

        # 3. Escribanos (control_escribanos = cta. cte. 130832-08)
        mask_escribanos = df["cta_cte"] == CTA_CTE_ESCRIBANOS

        df = df.loc[~(mask_obras | mask_honorarios | mask_escribanos)]
        logger.info(
            f"{etiqueta} → tras depurar obras/honorarios/escribanos: "
            f"{len(df)} filas"
        )

        # Unifica cta_cte con el nexo sgf_cta_cte (salida canónica). Los
        # masks anteriores se aplicaron sobre el valor crudo, igual que
        # los controles que ya cubren estas filas.
        df = await self.cta_cte_service.cta_cte_unifier(df, "sgf_cta_cte")

        if df.empty:
            logger.info(f"{etiqueta}: sin registros después de depurar (0 de {total}).")
            return []

        # Selección de columnas, límite y sanitización final
        columnas = [col for col in COLUMNAS_SGF if col in df.columns]
        df = df.loc[:, columnas]
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)
        logger.info(
            f"{etiqueta} → restantes: {len(df)} de {total} filas "
            f"({100 * len(df) / total:.1f}%)"
        )

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

ControlOtrosGastosSiifServiceDependency = Annotated[
    ControlOtrosGastosSiifService, Depends()
]
ControlOtrosGastosSgfServiceDependency = Annotated[
    ControlOtrosGastosSgfService, Depends()
]


@dataclass
# -------------------------------------------------
class ControlOtrosGastosExportService:
    """Export UNIFICADO de Otros Gastos: una sola ruta
    (``GET /control/otrosGastos/export``) sube un único Google Sheet
    con las 2 hojas de detalle (SIIF y SGF).

    Prioriza el snapshot persistido de cada tabla (POST posterior a
    ``/generate``) y cae al cómputo on-demand si el snapshot está vacío.
    """

    siif_service: ControlOtrosGastosSiifServiceDependency
    sgf_service: ControlOtrosGastosSgfServiceDependency

    # -------------------------------------------------
    async def export(
        self, params: ControlOtrosGastosExportFilter
    ) -> dict[str, Any]:
        """Encola la exportación unificada y responde de inmediato.

        Args:
            params: Filtro con el ``ejercicio`` a exportar.

        Returns:
            Acknowledge con título, detalle y la key destino.

        Raises:
            HTTPException: 400 si la key del Google Sheet aún no está
                definida o si falta ``ejercicio``.
        """
        if not SPREADSHEET_KEY_CONTROL_OTROS_GASTOS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google Sheet de Otros Gastos sin definir: complete "
                    "SPREADSHEET_KEY_CONTROL_OTROS_GASTOS en "
                    "src/analysis/services/control_otros_gastos.py."
                ),
            )
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio para exportar.",
            )

        asyncio.create_task(self._export_to_google_sheets(params))
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con las "
                f"hojas: {HOJA_SIIF} y {HOJA_SGF}."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_OTROS_GASTOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlOtrosGastosExportFilter
    ) -> None:
        """Tarea de fondo: sube las 2 hojas a UN único Google Sheet.

        En background no hay respuesta HTTP que retornar: cualquier
        error (incluido el 404 de "sin crudos SGF" del cómputo) se
        loguea para que sea visible en los logs de Koyeb; nada se traga
        en silencio.
        """
        search_siif = ControlOtrosGastosSiifFilter(
            ejercicio=params.ejercicio,
            limit=None,
        )
        search_sgf = ControlOtrosGastosSgfFilter(
            ejercicio=params.ejercicio,
            limit=None,
        )
        try:
            async with _export_lock:
                # 1. Snapshot con fallback al cómputo on-demand
                snapshot_siif = await self.siif_service.get_all(params=search_siif)
                if snapshot_siif:
                    df_siif = pd.DataFrame(
                        [doc.model_dump(by_alias=True) for doc in snapshot_siif]
                    )
                else:
                    filas = await self.siif_service.compute_otros_gastos_siif(
                        params=search_siif
                    )
                    df_siif = pd.DataFrame(filas)

                snapshot_sgf = await self.sgf_service.get_all(params=search_sgf)
                if snapshot_sgf:
                    df_sgf = pd.DataFrame(
                        [doc.model_dump(by_alias=True) for doc in snapshot_sgf]
                    )
                else:
                    filas = await self.sgf_service.compute_otros_gastos_sgf(
                        params=search_sgf
                    )
                    df_sgf = pd.DataFrame(filas)

                # 2. Una sola suba: ambas hojas al mismo key,
                #    descartando las hojas vacías
                sheets = []
                if not df_siif.empty:
                    sheets.append((df_siif, HOJA_SIIF))
                if not df_sgf.empty:
                    sheets.append((df_sgf, HOJA_SGF))

                if not sheets:
                    logger.warning(
                        "Otros Gastos: nada para exportar del ejercicio "
                        f"{params.ejercicio} (snapshots y cómputos vacíos)."
                    )
                    return

                # 3. Upload fuera del event loop (bloqueante)
                await run_in_threadpool(
                    upload_multiple_dataframes_to_google_sheets,
                    sheets,
                    spreadsheet_key=SPREADSHEET_KEY_CONTROL_OTROS_GASTOS,
                )
                logger.info(
                    "Otros Gastos: hojas "
                    f"{[nombre for _, nombre in sheets]} actualizadas en "
                    "Google Sheets"
                )
        except Exception as e:
            logger.error(
                "Otros Gastos: error en la exportación a Google Sheets "
                f"del ejercicio {params.ejercicio}: {e}"
            )


ControlOtrosGastosExportServiceDependency = Annotated[
    ControlOtrosGastosExportService, Depends()
]







