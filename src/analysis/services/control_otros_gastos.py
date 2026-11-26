__all__ = [
    "ControlOtrosGastosSiifService",
    "ControlOtrosGastosSiifServiceDependency",
    "ControlOtrosGastosSgfService",
    "ControlOtrosGastosSgfServiceDependency",
    "ControlOtrosGastosCruceService",
    "ControlOtrosGastosCruceServiceDependency",
    "ControlOtrosGastosExportService",
    "ControlOtrosGastosExportServiceDependency",
]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List, Tuple

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
from ...siif.schemas import (
    GtoRpa03gFullFilter,
    Rcg01UejpFullFilter,
    Rfondo07tpFullFilter,
)
from ...siif.services import (
    GtoRpa03gServiceDependency,
    Rcg01UejpServiceDependency,
    Rfondo07tpServiceDependency,
)
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
    ControlOtrosGastosCruceMensualRepositoryDependency,
    ControlOtrosGastosCruceRepositoryDependency,
    ControlOtrosGastosSgfRepositoryDependency,
    ControlOtrosGastosSiifRepositoryDependency,
)
from ..schemas import (
    ESTADO_PAREADO,
    ESTADO_SGF_SIN_SIIF,
    ESTADO_SIIF_SIN_SGF,
    ControlHonorariosFullFilter,
    ControlOtrosGastosCruceFilter,
    ControlOtrosGastosCruceGenerateFilter,
    ControlOtrosGastosCruceLiteFilter,
    ControlOtrosGastosCruceMensualFilter,
    ControlOtrosGastosCruceMensualReport,
    ControlOtrosGastosCruceReport,
    ControlOtrosGastosCruceSnapshot,
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
# En SGF este cuit liquida UN libramiento que AGREGA varios SIIF del
# mismo día: la Capa 1 agrupa esos SIIF por fecha y compara la SUMA
# contra el libramiento antes del pareo 1:1 normal.
CUIT_PAGOS_AGRUPADOS: str = "30500049460"

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

# Hojas del Google Sheet unificado (una por tabla del control).
HOJA_SIIF: str = "otros_gastos_siif"
HOJA_SGF: str = "otros_gastos_sgf"
# Capa 1: pareo 1:1 del resto (no fondos permanentes)
HOJA_CRUCE_RESTO: str = "otros_gastos_cruce_resto"
# Capa 2: control mensual de fondos permanentes
HOJA_CRUCE_FONDOS_PERM: str = "otros_gastos_cruce_fondos_perm"

# Orden de columnas de las tablas del cruce.
COLUMNAS_PAREOS: List[str] = [
    "ejercicio",
    "estado",
    "siif_nro_comprobante",
    "siif_fecha",
    "siif_mes",
    "siif_cuit",
    "siif_beneficiario",
    "siif_cta_cte",
    "siif_partida",
    "siif_importe",
    "sgf_libramiento",
    "sgf_fecha",
    "sgf_mes",
    "sgf_cuit",
    "sgf_beneficiario",
    "sgf_cta_cte",
    "sgf_importe_bruto",
    "dias_dif",
    "dif",
]
COLUMNAS_MENSUAL: List[str] = [
    "ejercicio",
    "mes",
    "siif_rendido",
    "sgf_pagado",
    "dif_mes",
    "siif_acum",
    "sgf_acum",
    "dif_acum",
    "dif_pct",
]

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()

# Icaro: tipos de comprobante que controla control_obras y que por lo
# tanto hay que depurar de SIIF por nro_comprobante. PA6 (subsistema de
# fondos) queda FUERA: no representa gasto de rcg01_uejp.
TIPOS_ICARO_OBRAS: List[str] = ["REG", "CYO"]

# PA6 = regularización de fondos (siif_rfondo07tp). NO sirve para el
# cruce de obras por nro_comprobante, pero SÍ para detectar gastos REG
# cuyo fondo ya fue regularizado en el mismo ejercicio (paso 4 de
# compute_otros_gastos_siif).
TIPO_COMPROBANTE_PA6: str = "PA6"

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
    rfondo07tp_service: Rfondo07tpServiceDependency
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

            # Visibilidad: si el POST trae filas que la validación
            # descartó, se avisa en logs (el detalle completo viaja en
            # la respuesta). Sin este warning, un snapshot parcial pasa
            # inadvertido (fue lo que dejó la tabla SIIF sin el resto).
            descartadas = len(data) - len(validation_result.validated)
            if descartadas > 0:
                logger.warning(
                    f"Otros Gastos SIIF: {descartadas} de {len(data)} filas "
                    "descartadas por validación en add_many. "
                    f"Primeros errores: {list(validation_result.errors)[:2]}"
                )

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
        4. Fondos regularizados por PA6: los ``clase_reg = "REG"``
           cuyo ``nro_fondo`` coincide con el ``nro_fondo`` de un PA6
           (``siif_rfondo07tp``, ``tipo_comprobante = "PA6"``) del
           MISMO ejercicio (no se cruzan PA6 de otros ejercicios).
        5. Obras: ``nro_comprobante`` de Icaro con ``tipo`` REG/CYO
           (el PA6 de Icaro no se usa: es subsistema de fondos).
        6. Haberes: cta. cte. 130832-04 sin las partidas 150/151
           (criterio de ``control_haberes``; se aplica sobre la cta_cte
           unificada porque el SIIF guarda "130832004" sin guiones).
        7. ART: ``clase_gto = "REM"`` con ``partida = "151"`` (no se
           carga en SGF ni lo cubre ``control_haberes``).
        8. Honorarios: criterio de ``get_siif_honorarios`` (grupo 3,
           sin partida 384, cuit INVICO, ctas 130832-05/07 y glosa
           HONOR/RECON/LOC con cta_cte unificada) más el
           ``nro_comprobante`` de Slave de ``control_honorarios``.
        9. Viáticos: ``nro_comprobante``/``nro_expte`` de
           ``control_viaticos`` (partidas 372/373).
        10. Débitos bancarios: ``nro_comprobante`` de
            ``control_debitos_bancarios`` (partida 355).
        11. Escribanos NO se depura de SIIF (impactan como fondos, no
            como gastos).
        12. Cajas chicas NO se depuran (criterio corregido): el
            reintegro de caja chica SÍ se carga en SGF, por lo que sus
            filas se conservan en SIIF y se parean uno a uno con el
            SGF en la Capa 1. El CUIT 30632351514 sigue distinguiendo
            los fondos permanentes (Capa 2, cruce mensual).

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

        # 4. Fondos regularizados por PA6: los REG cuyo nro_fondo
        #    coincide con el de un PA6 del MISMO ejercicio
        #    (siif_rfondo07tp) ya están regularizados. Corre antes de
        #    obras para que el log refleje su aporte (los PA6 mismos
        #    no están en el df: son otra colección, de fondos).
        pa6_params = Rfondo07tpFullFilter(
            tipo_comprobante=TIPO_COMPROBANTE_PA6,
            ejercicio=str(ejercicio),
            limit=None,
        )
        pa6_docs = await self.rfondo07tp_service.get_all(params=pa6_params)
        # nro_fondo es SIEMPRE el número como str sin ceros a la
        # izquierda (igual en rfondo07tp y en rcg01_uejp): comparación
        # literal, sin normalizar.
        fondos_pa6 = {doc.nro_fondo for doc in pa6_docs or [] if doc.nro_fondo}
        if fondos_pa6:
            antes = len(df)
            mask_fondos = (df["clase_reg"] == "REG") & df["nro_fondo"].isin(fondos_pa6)
            df = df.loc[~mask_fondos]
            logger.info(
                f"{etiqueta} → fondos PA6 (regularizados): {antes - len(df)} filas"
            )

        # 5. Obras: nro_comprobante de Icaro REG/CYO (sin PA6)
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

        # 6. Haberes: cta_cte 130832-04 sin las partidas 150/151
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

        # 7. ART: clase_gto REM con partida 151 — no se carga en SGF ni
        #    lo cubre control_haberes (que excluye 150/151 de sus
        #    haberes), por lo que quedaría como "otro gasto" sin ningún
        #    control que lo respalde.
        antes = len(df)
        mask_art = (df["clase_gto"] == "REM") & (df["partida"] == "151")
        df = df.loc[~mask_art]
        logger.info(f"{etiqueta} → ART: {antes - len(df)} filas")

        # 8. Honorarios: criterio de get_siif_honorarios con cta_cte
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

        # 9. Viáticos: nro_comprobante y nro_expte de control_viaticos
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

        # 10. Débitos bancarios: nro_comprobante de control_debitos_
        #     bancarios (partida 355).
        debitos = await self.debitos_service.generate_siif_debitos(ejercicio=ejercicio)
        if (
            debitos is not None
            and not debitos.empty
            and ("nro_comprobante" in debitos.columns)
        ):
            antes = len(df)
            nros_debitos = set(debitos["nro_comprobante"].dropna())
            df = df.loc[~df["nro_comprobante"].isin(nros_debitos)]
            logger.info(f"{etiqueta} → débitos bancarios: {antes - len(df)} filas")

        # 11-12. Escribanos y cajas chicas NO se depuran (ver
        #     docstring): las cajas chicas SÍ se cargan en SGF, por lo
        #     que se conservan para el pareo 1:1 de la Capa 1.

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

            # Visibilidad: si el POST trae filas que la validación
            # descartó, se avisa en logs (el detalle completo viaja en
            # la respuesta). Sin este warning, un snapshot parcial pasa
            # inadvertido (fue lo que dejó la tabla SGF sin cuit nulos).
            descartadas = len(data) - len(validation_result.validated)
            if descartadas > 0:
                logger.warning(
                    f"Otros Gastos SGF: {descartadas} de {len(data)} filas "
                    "descartadas por validación en add_many. "
                    f"Primeros errores: {list(validation_result.errors)[:2]}"
                )

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
            f"{etiqueta} → tras depurar obras/honorarios/escribanos: {len(df)} filas"
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


# --------------------------------------------------
# Helpers del cruce SIIF <-> SGF
# --------------------------------------------------
def _normalizar_cuit(valores: pd.Series) -> pd.Series:
    """cuit como texto limpio: numéricos sin decimales (3.0632e10 →
    '30632351514') y None cuando falta."""

    def _texto(valor: Any) -> Any:
        if pd.isna(valor):
            return None
        if isinstance(valor, float):
            return str(int(valor))
        return str(valor).strip()

    return valores.map(_texto)


def _clave_mes(mes: Any) -> int:
    """Ordena 'MM/YYYY' cronológicamente (0 si está mal formado)."""
    try:
        mes_num, anio = str(mes).split("/")
        return int(anio) * 100 + int(mes_num)
    except (ValueError, AttributeError):
        return 0


def _a_registros(df: pd.DataFrame, columnas: List[str]) -> List[dict]:
    """Selección de columnas + sanitización JSON (patrón del módulo)."""
    if df.empty:
        return []
    df = df.loc[:, [col for col in columnas if col in df.columns]]
    df = sanitize_dataframe_for_json_with_datetime(df)
    return df.replace({np.nan: None}).to_dict(orient="records")


def _lado_siif(ejercicio: int, estado: str, fila: Any) -> dict:
    """Lado SIIF de una fila del pareo (``fila``: Series o dict vacío)."""
    get = fila.get if hasattr(fila, "get") else lambda *_: None
    return {
        "ejercicio": ejercicio,
        "estado": estado,
        "siif_nro_comprobante": get("nro_comprobante"),
        "siif_fecha": get("fecha"),
        "siif_mes": get("mes"),
        "siif_cuit": get("cuit_n"),
        "siif_beneficiario": get("beneficiario"),
        "siif_cta_cte": get("cta_cte"),
        "siif_partida": get("partida"),
        "siif_importe": get("importe"),
    }


def _lado_sgf(ejercicio: int, estado: str, fila: Any) -> dict:
    """Lado SGF de una fila del pareo (``fila``: Series o dict vacío)."""
    get = fila.get if hasattr(fila, "get") else lambda *_: None
    return {
        "ejercicio": ejercicio,
        "estado": estado,
        "sgf_libramiento": get("libramiento"),
        "sgf_fecha": get("fecha"),
        "sgf_mes": get("mes"),
        "sgf_cuit": get("cuit_n"),
        "sgf_beneficiario": get("beneficiario"),
        "sgf_cta_cte": get("cta_cte"),
        "sgf_importe_bruto": get("importe_bruto"),
    }


# --------------------------------------------------
def _parear_grupo(
    ejercicio: int,
    grupo: pd.DataFrame,
    df_sgf: pd.DataFrame,
    importe_tol: float,
    ventana_dias: int,
    pareos: List[dict],
) -> bool:
    """Parea un grupo de filas de SIIF contra UN libramiento de SGF.

    Los pre-pasos de la Capa 1 agrupan filas que en SGF se liquidan en
    un solo libramiento: el comprobante con varias imputaciones (una
    fila por partida), los comprobantes del mismo cuit en el mismo día
    o en una ventana de días, y el cuit de pago agregado por día. La
    SUMA de los importes del grupo se compara contra los libramientos
    no usados del MISMO cuit con las tolerancias del cruce
    (|diferencia| ≤ ``importe_tol`` en pesos sobre la suma y fecha
    ±``ventana_dias``).

    Si matchea: marca el libramiento como usado (queda fuera de la
    Capa 2), agrega una fila ``PAREADO`` por cada fila del grupo —con
    ``dif`` igual al residuo de la suma— y devuelve ``True``. Si no
    matchea (o el grupo tiene importes/fecha ilegibles), devuelve
    ``False`` y las filas siguen disponibles para los pasos
    siguientes y para el pareo 1:1.

    Args:
        ejercicio: Ejercicio del bloque.
        grupo: Filas de SIIF a agrupar (subconjunto de ``resto``).
        df_sgf: Tabla SGF con la columna ``_usado`` (se marca en ella).
        importe_tol: Tolerancia ABSOLUTA en pesos sobre la suma
            (0.05 = 5 centavos).
        ventana_dias: Ventana máxima en días entre fechas (0 = sin).
        pareos: Lista de salida; se le agregan las filas del pareo.

    Returns:
        ``True`` si el grupo matcheó un libramiento.
    """
    importes = pd.to_numeric(grupo["importe"], errors="coerce")
    if importes.isna().any():
        return False
    suma_grupo = float(importes.sum())
    cuit_grupo = grupo["cuit_n"].iloc[0]
    candidatos = df_sgf.loc[(~df_sgf["_usado"]) & (df_sgf["cuit_n"] == cuit_grupo)]
    candidatos = candidatos.loc[
        (candidatos["importe_bruto"] - suma_grupo).abs() <= importe_tol
    ]
    # Misma fecha para todo el grupo (agrupado por día); con
    # comprobantes multi-imputación puede haber NaT si todas las
    # filas fallan el parseo.
    fecha_grupo = grupo["fecha_d"].min()
    if ventana_dias > 0:
        if pd.isna(fecha_grupo):
            # Sin fecha no se puede aplicar la ventana: al 1:1.
            return False
        candidatos = candidatos.loc[candidatos["fecha_d"].notna()]
        candidatos = candidatos.loc[
            (candidatos["fecha_d"] - fecha_grupo).abs()
            <= pd.Timedelta(days=ventana_dias)
        ]
    if candidatos.empty:
        return False

    comparacion = candidatos.assign(
        _dif=(candidatos["importe_bruto"] - suma_grupo).abs(),
        _dias=(candidatos["fecha_d"] - fecha_grupo).abs(),
    ).sort_values(["_dias", "_dif"])
    indice_sgf = comparacion.index[0]
    fila_sgf = df_sgf.loc[indice_sgf]
    df_sgf.loc[indice_sgf, "_usado"] = True
    dias_dif = None
    if pd.notna(fecha_grupo) and pd.notna(fila_sgf["fecha_d"]):
        dias_dif = int((fila_sgf["fecha_d"] - fecha_grupo).days)
    for indice_fila in grupo.index:
        pareos.append(
            {
                **_lado_siif(ejercicio, ESTADO_PAREADO, grupo.loc[indice_fila]),
                **_lado_sgf(ejercicio, ESTADO_PAREADO, fila_sgf),
                "dias_dif": dias_dif,
                "dif": suma_grupo - float(fila_sgf["importe_bruto"]),
            }
        )
    return True


@dataclass
# -------------------------------------------------
class ControlOtrosGastosCruceService:
    """Cruce SIIF <-> SGF en dos capas sobre las tablas depuradas.

    Capa 1 (``pareos``): pareo 1:1 del "resto" de SIIF (todo lo que NO
    es fondo permanente) contra SGF, con estados ``PAREADO``,
    ``SIIF_SIN_SGF`` y ``SGF_SIN_SIIF``.

    Capa 2 (``mensual``): fondos permanentes de SIIF (``clase_reg =
    "REG"`` con cuit INVICO) contra TODO el SGF no pareado en la
    Capa 1 (incluidas las huérfanas), mes a mes, con acumulados.
    """

    cruce_repository: ControlOtrosGastosCruceRepositoryDependency
    cruce_mensual_repository: ControlOtrosGastosCruceMensualRepositoryDependency
    siif_service: ControlOtrosGastosSiifServiceDependency
    sgf_service: ControlOtrosGastosSgfServiceDependency

    # -------------------------------------------------
    async def generate(self, params: ControlOtrosGastosCruceGenerateFilter) -> dict:
        """Cruce on-demand (sin persistir; el snapshot lo congela el
        POST posterior).

        Args:
            params: ``ejercicio`` + tolerancias del pareo.

        Returns:
            ``{"ejercicio", "pareos": [...], "mensual": [...]}``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")
        compute_params = ControlOtrosGastosCruceFilter(
            ejercicio=params.ejercicio,
            limit=None,
        )
        return await self.compute_cruce(
            params=compute_params,
            importe_tol=params.importe_tol,
            ventana_dias=params.ventana_dias,
            ventana_agrupacion_dias=params.ventana_agrupacion_dias,
        )

    # -------------------------------------------------
    async def get_snapshot(self, params: ControlOtrosGastosCruceFilter) -> dict:
        """Lee los snapshots de AMBAS colecciones del cruce."""
        search_pareos = ControlOtrosGastosCruceFilter(
            ejercicio=params.ejercicio,
            limit=None,
        )
        search_mensual = ControlOtrosGastosCruceMensualFilter(
            ejercicio=params.ejercicio,
            limit=None,
        )
        pareos = await self.cruce_repository.find_with_filter_params(
            params=search_pareos
        )
        mensual = await self.cruce_mensual_repository.find_with_filter_params(
            params=search_mensual
        )
        return {
            "ejercicio": params.ejercicio,
            "pareos": [doc.model_dump(mode="json", exclude={"id"}) for doc in pareos],
            "mensual": [doc.model_dump(mode="json", exclude={"id"}) for doc in mensual],
        }

    # -------------------------------------------------
    async def add_many(
        self, data: ControlOtrosGastosCruceSnapshot
    ) -> RouteReturnSchema:
        """Persiste AMBAS tablas del cruce con borrado idempotente por
        ``ejercicio`` (contraparte del GET /cruce/generate).

        Args:
            data: Snapshot con las filas ``pareos`` y ``mensual``.

        Returns:
            ``RouteReturnSchema`` combinando las 2 colecciones.

        Raises:
            HTTPException: 400 si el snapshot está vacío o ninguna fila
                es válida.
        """
        if not data.pareos and not data.mensual:
            raise HTTPException(
                status_code=400,
                detail="El snapshot del cruce está vacío (pareos y mensual).",
            )
        try:
            validacion_pareos = validate_and_extract_data_from_list(
                data_list=data.pareos,
                model=ControlOtrosGastosCruceReport,
                field_id=["ejercicio", "estado", "siif_nro_comprobante"],
            )
            validacion_mensual = validate_and_extract_data_from_list(
                data_list=data.mensual,
                model=ControlOtrosGastosCruceMensualReport,
                field_id=["ejercicio", "mes"],
            )
            if (data.pareos and not validacion_pareos.validated) or (
                data.mensual and not validacion_mensual.validated
            ):
                errores = list(validacion_pareos.errors) + list(
                    validacion_mensual.errors
                )
                detalle = "No se encontraron registros válidos para procesar."
                if errores:
                    detalle += f" Errores detectados: {errores[:2]}"
                raise HTTPException(status_code=400, detail=detalle)

            resultado = RouteReturnSchema(title="Sincronización Otros Gastos Cruce")
            delete_filter = {"ejercicio": data.ejercicio}
            for validacion, repositorio, etiqueta_lado in (
                (
                    validacion_pareos,
                    self.cruce_repository,
                    "Otros Gastos Cruce Pareos",
                ),
                (
                    validacion_mensual,
                    self.cruce_mensual_repository,
                    "Otros Gastos Cruce Mensual",
                ),
            ):
                parcial = await sync_validated_to_repository(
                    repository=repositorio,
                    validation=validacion,
                    delete_filter=delete_filter,
                    title="Sincronización Otros Gastos Cruce",
                    label=etiqueta_lado,
                    logger=logger,
                )
                resultado.added += parcial.added
                resultado.deleted += parcial.deleted
                resultado.errors += parcial.errors
            return resultado

        except HTTPException:
            # Respeta los 400 de "snapshot vacío" / "sin válidos"
            raise
        except Exception as e:
            logger.error(f"Error durante el proceso de add_many del cruce: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error sincronizando el cruce de Otros Gastos: {e}",
            )

    # -------------------------------------------------
    async def delete_many(self, params: ControlOtrosGastosCruceLiteFilter) -> dict:
        """Borra AMBAS colecciones del cruce por ``ejercicio``.

        Args:
            params: Filtro con el ``ejercicio`` a borrar.

        Returns:
            Resumen ``RouteReturnSchema`` (deleted = filas de las 2
            colecciones).

        Raises:
            HTTPException: 400 si falta ``ejercicio``.
        """
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio para borrar.",
            )
        filtro = {"ejercicio": params.ejercicio}
        borrados_pareos = await self.cruce_repository.delete_by_fields(filtro)
        borrados_mensual = await self.cruce_mensual_repository.delete_by_fields(filtro)
        return {
            "title": "Eliminación Otros Gastos Cruce",
            "added": 0,
            "deleted": borrados_pareos + borrados_mensual,
            "errors": [],
        }

    # -------------------------------------------------
    async def _cargar_tablas_depuradas(
        self, ejercicio: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Tablas depuradas SIIF y SGF: snapshot con fallback al
        cómputo on-demand (mismo patrón que el export unificado)."""
        search_siif = ControlOtrosGastosSiifFilter(
            ejercicio=ejercicio,
            limit=None,
        )
        snapshot_siif = await self.siif_service.get_all(params=search_siif)
        if snapshot_siif:
            df_siif = pd.DataFrame([doc.model_dump() for doc in snapshot_siif])
        else:
            df_siif = pd.DataFrame(
                await self.siif_service.compute_otros_gastos_siif(params=search_siif)
            )

        search_sgf = ControlOtrosGastosSgfFilter(
            ejercicio=ejercicio,
            limit=None,
        )
        snapshot_sgf = await self.sgf_service.get_all(params=search_sgf)
        if snapshot_sgf:
            df_sgf = pd.DataFrame([doc.model_dump() for doc in snapshot_sgf])
        else:
            df_sgf = pd.DataFrame(
                await self.sgf_service.compute_otros_gastos_sgf(params=search_sgf)
            )

        for marco in (df_siif, df_sgf):
            marco.drop(columns=["id", "_id"], errors="ignore", inplace=True)
        return df_siif, df_sgf

    # -------------------------------------------------
    async def compute_cruce(
        self,
        params: ControlOtrosGastosCruceFilter,
        importe_tol: float = 0.05,
        ventana_dias: int = 30,
        ventana_agrupacion_dias: int = 10,
    ) -> dict:
        """Cruce SIIF <-> SGF en dos capas (on-demand).

        Capa 1 - ``pareos``: pareo 1:1 greedy (y determinístico: orden
        por fecha/nro_comprobante) del resto de SIIF (todo lo que NO es
        fondo permanente) contra SGF: ``cuit`` + |diferencia de
        importe| ≤ ``importe_tol`` (tolerancia ABSOLUTA en pesos, no
        porcentual) + fecha ±``ventana_dias``. Antes del 1:1 corren
        CUATRO pre-pasos (orden estricto-primero) que agrupan filas de
        SIIF y comparan la SUMA contra UN libramiento con las MISMAS
        tolerancias (``dif`` = residuo de la suma; si el grupo no
        matchea, sus filas siguen a los pasos siguientes y al 1:1):

        1. Comprobantes multi-imputación: un ``nro_comprobante`` del
           mismo cuit con varias filas (UNA POR PARTIDA) se agrupa por
           (cuit, comprobante) y su suma se cruza con el libramiento.
           Los fondos permanentes (REG + cuit INVICO + nro_fondo) no
           llegan acá: el ``resto`` ya los excluye.
        2. Varios comprobantes del mismo cuit y día: SGF agrega
           comprobantes distintos de un mismo beneficiario en un
           libramiento (p.ej. 00435/26 + 00436/26 ↔ 31628): se
           agrupan por (cuit, fecha) los pendientes con más de un
           comprobante distinto y su suma se cruza con el libramiento.
        3. Ventanas de comprobantes del mismo cuit
           (``ventana_agrupacion_dias``, 10 por defecto; 0 = solo mismo
           día): la unidad de agrupación es el COMPROBANTE completo y
           se prueban todas las ventanas contiguas con span ≤ N días
           (p.ej. 00835/26 + 00891..00895/26 ↔ 31826, o 00451/26 +
           00387/26 en 18-20/03 ↔ un libramiento que abarca ambos
           días). Generaliza el pre-paso 4 a todos los cuits.
        4. Pagos agrupados por día: los SIIF del cuit
           ``CUIT_PAGOS_AGRUPADOS`` se agrupan por fecha exacta. Es la
           red de seguridad del pre-paso 3: si la fusión por ventana
           no matcheó donde el día exacto sí, lo resuelve acá.

        Estados: ``PAREADO``, ``SIIF_SIN_SGF`` y ``SGF_SIN_SIIF`` (SGF
        no usado cuyo cuit aparece en el resto SIIF: dominio de pagos
        directos).

        Capa 2 - ``mensual``: fondos permanentes de SIIF (``clase_reg =
        "REG"`` con cuit INVICO) contra TODO el SGF no pareado en la
        Capa 1 —incluidas las huérfanas ``SGF_SIN_SIIF``, que también
        podrían ser pagos de fondo— mes a mes, con acumulados y
        ``dif_pct`` (% sobre el SGF acumulado).

        Args:
            params: Filtro con el ``ejercicio``.
            importe_tol: Tolerancia ABSOLUTA del pareo por importe, en
            pesos (0.05 = 5 centavos por defecto).
            ventana_dias: Ventana máxima en días entre fechas (0 = sin
                ventana).
            ventana_agrupacion_dias: Ventana máxima en días para
                agrupar comprobantes del mismo cuit en el pre-paso 3
                (0 = solo mismo día; 10 = por defecto).

        Returns:
            ``{"ejercicio", "pareos": [...], "mensual": [...]}``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio: int = params.ejercicio
        etiqueta: str = f"Otros Gastos Cruce {ejercicio}"

        df_siif, df_sgf = await self._cargar_tablas_depuradas(ejercicio)
        if df_siif.empty:
            logger.info(f"{etiqueta}: sin tabla SIIF depurada; cruce vacío.")
            return {"ejercicio": ejercicio, "pareos": [], "mensual": []}

        df_siif = df_siif.copy()
        df_siif["cuit_n"] = _normalizar_cuit(df_siif["cuit"])
        df_siif["fecha_d"] = pd.to_datetime(
            df_siif["fecha"], dayfirst=True, errors="coerce"
        )

        if df_sgf.empty:
            # Marco vacío con las columnas que el resto del método usa.
            df_sgf = pd.DataFrame(
                columns=[
                    "libramiento",
                    "fecha",
                    "mes",
                    "cuit",
                    "cuit_n",
                    "beneficiario",
                    "cta_cte",
                    "importe_bruto",
                    "fecha_d",
                    "_usado",
                ]
            )
        else:
            df_sgf = df_sgf.copy()
            df_sgf["cuit_n"] = _normalizar_cuit(df_sgf["cuit"])
            df_sgf["fecha_d"] = pd.to_datetime(
                df_sgf["fecha"], dayfirst=True, errors="coerce"
            )
            df_sgf["_usado"] = False

        es_fondo_permanente = (df_siif["clase_reg"] == "REG") & (
            df_siif["cuit_n"] == CUIT_INVICO
        )
        perm = df_siif.loc[es_fondo_permanente]
        resto = df_siif.loc[~es_fondo_permanente]
        logger.info(
            f"{etiqueta} → fondos permanentes: {len(perm)} filas | "
            f"resto: {len(resto)} filas"
        )

        # ---- Capa 1: pareo 1:1 del resto -------------------------
        pareos: List[dict] = []
        orden = resto.sort_values(
            ["fecha", "nro_comprobante"], na_position="last"
        ).index

        # Capa 1: pre-pasos de agrupación en orden estricto-primero +
        # greedy. Todos agrupan filas de SIIF y comparan la SUMA contra
        # UN libramiento con _parear_grupo; si el grupo no matchea, sus
        # filas quedan pendientes para los pasos siguientes.
        pareadas_agrupadas: set = set()

        # Pre-paso 1: comprobantes con varias imputaciones. Un mismo
        # nro_comprobante en SIIF tiene UNA FILA POR PARTIDA y SGF
        # liquida UN importe por comprobante: se agrupan por (cuit,
        # nro_comprobante) —agrupar también por cuit evita sumar
        # imputaciones de cuits distintos con el mismo número— y la
        # SUMA se compara con el libramiento (_parear_grupo). Los
        # fondos permanentes (REG + cuit INVICO + nro_fondo) no llegan
        # acá: ya están fuera del ``resto``. Los grupos que no matchean
        # caen a los pasos siguientes.
        pendientes = resto.loc[~resto.index.isin(pareadas_agrupadas)]
        grupos_comp: int = 0
        filas_comp: int = 0
        for _llave, grupo in pendientes.groupby(
            ["cuit_n", "nro_comprobante"], sort=True
        ):
            if len(grupo) < 2:
                continue  # imputación única: la resuelve el 1:1 normal
            if _parear_grupo(
                ejercicio, grupo, df_sgf, importe_tol, ventana_dias, pareos
            ):
                grupos_comp += 1
                filas_comp += len(grupo)
                pareadas_agrupadas.update(grupo.index)
        if grupos_comp:
            logger.info(
                f"{etiqueta} → comprobantes multi-imputación: "
                f"{grupos_comp} grupos / {filas_comp} filas SIIF"
            )

        # Pre-paso 2: varios comprobantes del MISMO cuit en el MISMO
        # día. Algunos libramientos de SGF agregan varios comprobantes
        # de un mismo beneficiario: p.ej. 00435/26 + 00436/26 = 211.840
        # ↔ libramiento 31628. Se agrupan por (cuit, fecha) los
        # pendientes con más de un comprobante distinto y la SUMA se
        # compara con el libramiento (_parear_grupo). Los grupos con un
        # solo comprobante ya los intentó el pre-paso 1; lo que no
        # matchea acá cae a los pasos siguientes y al pareo 1:1.
        pendientes_dia = resto.loc[~resto.index.isin(pareadas_agrupadas)]
        fecha_valida_dia = (
            pendientes_dia["fecha"].fillna("").astype(str).str.strip().ne("")
        )
        agrupables_dia = pendientes_dia.loc[fecha_valida_dia]
        grupos_dia: int = 0
        filas_dia: int = 0
        for _llave, grupo in agrupables_dia.groupby(["cuit_n", "fecha"], sort=True):
            if grupo["nro_comprobante"].nunique() < 2:
                continue  # 1 solo comprobante: lo intentó el pre-paso 1
            if _parear_grupo(
                ejercicio, grupo, df_sgf, importe_tol, ventana_dias, pareos
            ):
                grupos_dia += 1
                filas_dia += len(grupo)
                pareadas_agrupadas.update(grupo.index)
        if grupos_dia:
            logger.info(
                f"{etiqueta} → varios comprobantes del mismo día: "
                f"{grupos_dia} grupos / {filas_dia} filas SIIF"
            )

        # Pre-paso 3: ventanas deslizantes de comprobantes del mismo
        # cuit (``ventana_agrupacion_dias``). Generaliza el pre-paso 4 a
        # TODOS los cuits: la unidad de agrupación es el COMPROBANTE
        # completo (agrupación primaria por nro_comprobante) y se
        # prueban TODAS las ventanas contiguas [i..j] con span ≤ N días
        # en orden de fecha — no un corte fijo, que puede partir el
        # grupo justo donde no calza. Ej.: 00835/26 (29/04) +
        # 00891+00893+00894+00895 (05/05) = 2.794.117,89 ↔ 31826, o
        # 00451/26 + 00387/26 (18-20/03) ↔ un libramiento que abarca
        # ambos días. Ventana 0 = solo mismo día (equivale al pre-paso
        # 2). Lo que no matchea acá cae a los pasos siguientes y al
        # pareo 1:1.
        pendientes_ventana = resto.loc[~resto.index.isin(pareadas_agrupadas)]
        fecha_valida_ventana = (
            pendientes_ventana["fecha"].fillna("").astype(str).str.strip().ne("")
        )
        agrupables_ventana = pendientes_ventana.loc[
            fecha_valida_ventana & pendientes_ventana["fecha_d"].notna()
        ]
        grupos_ventana: int = 0
        filas_ventana: int = 0

        def _probar_ventana(unidades: List[pd.DataFrame]) -> bool:
            """Suma ``unidades`` (comprobantes) y la enfrenta a UN
            libramiento; si matchea, agrega sus filas al pareo."""
            nonlocal grupos_ventana, filas_ventana
            if not unidades:
                return False
            grupo = pd.concat(unidades)
            if not _parear_grupo(
                ejercicio, grupo, df_sgf, importe_tol, ventana_dias, pareos
            ):
                return False
            grupos_ventana += 1
            filas_ventana += len(grupo)
            pareadas_agrupadas.update(grupo.index)
            return True

        # Ventanas DESLIZANTES: en vez de partir las unidades en
        # clústeres fijos (los cortes pueden dejar afuera el subconjunto
        # que calza, p.ej. 00835/26 (29/04) + 00891+00893+00894+00895
        # (05/05) = 2.794.117,89 ↔ 31826), se prueban TODAS las
        # ventanas contiguas [i..j] con span ≤ ``ventana_agrupacion_dias``
        # en orden de fecha. La suma se prefiltra contra los importes de
        # los libramientos sin usar del cuit y recién entonces se
        # enfrenta a _parear_grupo (que valida además la ventana de
        # fechas y marca el libramiento como usado). Unidades ya
        # pareadas se saltean: la ventana solo suma filas pendientes.
        for _cuit, subgrupo in agrupables_ventana.groupby("cuit_n", sort=True):
            subgrupo = subgrupo.sort_values(
                ["fecha_d", "nro_comprobante"], na_position="last"
            )
            claves = subgrupo["nro_comprobante"].map(
                lambda valor: "__SIN__" if pd.isna(valor) else str(valor).strip()
            )
            unidades: List[dict] = []
            for clave, filas in subgrupo.groupby(claves, sort=False):
                unidades.append(
                    {
                        "fecha": filas["fecha_d"].min(),
                        "clave": clave,
                        "filas": filas,
                        "suma": float(
                            pd.to_numeric(filas["importe"], errors="coerce").sum()
                        ),
                        "comps": {clave},
                    }
                )
            unidades.sort(key=lambda unidad: (unidad["fecha"], unidad["clave"]))
            brutos = df_sgf.loc[
                (~df_sgf["_usado"]) & (df_sgf["cuit_n"] == _cuit), "importe_bruto"
            ].to_numpy(dtype=float)
            pendiente = [True] * len(unidades)
            inicio = 0
            while inicio < len(unidades):
                if not pendiente[inicio]:
                    inicio += 1
                    continue
                acum: List[pd.DataFrame] = []
                suma = 0.0
                comps: set = set()
                indice = inicio
                while (
                    indice < len(unidades)
                    and unidades[indice]["fecha"] - unidades[inicio]["fecha"]
                    <= pd.Timedelta(days=ventana_agrupacion_dias)
                ):
                    if pendiente[indice]:
                        acum.append(unidades[indice]["filas"])
                        suma += unidades[indice]["suma"]
                        comps |= unidades[indice]["comps"]
                    # Al menos 2 comprobantes: un comprobante con varias
                    # filas ya lo intentó el pre-paso 1.
                    if (
                        len(acum) >= 2
                        and len(comps) >= 2
                        and np.isfinite(suma)
                        and (np.abs(brutos - suma) <= importe_tol).any()
                        and _probar_ventana(acum)
                    ):
                        for rango in range(inicio, indice + 1):
                            pendiente[rango] = False
                        break
                    indice += 1
                inicio += 1
        if grupos_ventana:
            logger.info(
                f"{etiqueta} → comprobantes en ventana de "
                f"{ventana_agrupacion_dias} días: {grupos_ventana} grupos / "
                f"{filas_ventana} filas SIIF"
            )

        # Pre-paso 4 (antes pre-paso 1): pagos agrupados por día. El
        # CUIT_PAGOS_AGRUPADOS liquida en SGF UN libramiento que agrega
        # varios SIIF del mismo día. Queda el ÚLTIMO como red de
        # seguridad: si el pre-paso 3 fusionó días que matchean por
        # separado, acá se reintenta con el día exacto.
        fecha_valida = resto["fecha"].fillna("").astype(str).str.strip().ne("")
        siif_agrupados = resto.loc[
            (resto["cuit_n"] == CUIT_PAGOS_AGRUPADOS)
            & fecha_valida
            & ~resto.index.isin(pareadas_agrupadas)
        ]
        grupos_cuit: int = 0
        filas_cuit: int = 0
        for _fecha_txt, grupo in siif_agrupados.groupby("fecha", sort=True):
            if len(grupo) < 2:
                continue  # 1 sola fila del día: la resuelve el 1:1 normal
            if _parear_grupo(
                ejercicio, grupo, df_sgf, importe_tol, ventana_dias, pareos
            ):
                grupos_cuit += 1
                filas_cuit += len(grupo)
                pareadas_agrupadas.update(grupo.index)
        if grupos_cuit:
            logger.info(
                f"{etiqueta} → pagos agrupados ({CUIT_PAGOS_AGRUPADOS}): "
                f"{grupos_cuit} grupos / {filas_cuit} filas SIIF"
            )

        for indice in orden:
            if indice in pareadas_agrupadas:
                continue  # ya pareada en un pre-paso de agrupación
            fila = resto.loc[indice]
            importe_siif = fila.get("importe")
            candidatos = df_sgf.loc[
                (~df_sgf["_usado"]) & (df_sgf["cuit_n"] == fila["cuit_n"])
            ]
            if pd.isna(importe_siif):
                candidatos = candidatos.iloc[0:0]
            else:
                candidatos = candidatos.loc[
                    (candidatos["importe_bruto"] - float(importe_siif)).abs()
                    <= importe_tol
                ]
                if ventana_dias > 0:
                    candidatos = candidatos.loc[candidatos["fecha_d"].notna()]
                    if pd.notna(fila["fecha_d"]):
                        candidatos = candidatos.loc[
                            (candidatos["fecha_d"] - fila["fecha_d"]).abs()
                            <= pd.Timedelta(days=ventana_dias)
                        ]

            if candidatos.empty:
                pareos.append(_lado_siif(ejercicio, ESTADO_SIIF_SIN_SGF, fila))
                continue

            comparacion = candidatos.assign(
                _dif=(candidatos["importe_bruto"] - float(importe_siif)).abs(),
                _dias=(candidatos["fecha_d"] - fila["fecha_d"]).abs(),
            ).sort_values(["_dias", "_dif"])
            indice_sgf = comparacion.index[0]
            fila_sgf = df_sgf.loc[indice_sgf]
            df_sgf.loc[indice_sgf, "_usado"] = True
            dias_dif = None
            if pd.notna(fila["fecha_d"]) and pd.notna(fila_sgf["fecha_d"]):
                dias_dif = int((fila_sgf["fecha_d"] - fila["fecha_d"]).days)
            pareos.append(
                {
                    **_lado_siif(ejercicio, ESTADO_PAREADO, fila),
                    **_lado_sgf(ejercicio, ESTADO_PAREADO, fila_sgf),
                    "dias_dif": dias_dif,
                    "dif": float(importe_siif) - float(fila_sgf["importe_bruto"]),
                }
            )

        # SGF no usado dentro del dominio del resto (cuit presentes en
        # el resto SIIF, matcheado o no) → huérfanos del lado SGF.
        cuits_resto = set(resto["cuit_n"].dropna())
        sin_usar = df_sgf.loc[~df_sgf["_usado"]]
        huerfanas_sgf = sin_usar.loc[sin_usar["cuit_n"].isin(cuits_resto)]
        for indice in huerfanas_sgf.index:
            pareos.append(_lado_sgf(ejercicio, ESTADO_SGF_SIN_SIIF, df_sgf.loc[indice]))
        logger.info(
            f"{etiqueta} → pareos: {len(pareos)} filas "
            f"(SGF huérfanas del resto: {len(huerfanas_sgf)})"
        )

        # ---- Capa 2: fondos permanentes mes a mes -----------------
        # TODO el SGF no pareado en la Capa 1, incluidas las huérfanas
        # SGF_SIN_SIIF: un pago con cuit del dominio del resto también
        # podría ser de fondo permanente (su cuit es de un proveedor
        # que además figura en pagos directos). Las huérfanas siguen
        # siendo filas de la Capa 1; acá solo cuentan sus importes.
        sgf_fondo = df_sgf.loc[~df_sgf["_usado"]]
        siif_rendido = perm.groupby("mes")["importe"].sum()
        sgf_pagado = sgf_fondo.groupby("mes")["importe_bruto"].sum()

        meses = sorted(set(siif_rendido.index) | set(sgf_pagado.index), key=_clave_mes)
        filas_mensual: List[dict] = []
        acum_siif: float = 0.0
        acum_sgf: float = 0.0
        for mes in meses:
            rendido = float(siif_rendido.get(mes, 0.0))
            pagado = float(sgf_pagado.get(mes, 0.0))
            acum_siif += rendido
            acum_sgf += pagado
            dif_acum = acum_siif - acum_sgf
            filas_mensual.append(
                {
                    "ejercicio": ejercicio,
                    "mes": mes,
                    "siif_rendido": rendido,
                    "sgf_pagado": pagado,
                    "dif_mes": rendido - pagado,
                    "siif_acum": acum_siif,
                    "sgf_acum": acum_sgf,
                    "dif_acum": dif_acum,
                    "dif_pct": (100.0 * dif_acum / acum_sgf) if acum_sgf else None,
                }
            )
        logger.info(
            f"{etiqueta} → mensual: {len(filas_mensual)} meses | "
            f"SIIF rendido {acum_siif:,.0f} | SGF pagado {acum_sgf:,.0f} | "
            f"dif acum {acum_siif - acum_sgf:,.0f}"
        )

        return {
            "ejercicio": ejercicio,
            "pareos": _a_registros(pd.DataFrame(pareos), COLUMNAS_PAREOS),
            "mensual": _a_registros(pd.DataFrame(filas_mensual), COLUMNAS_MENSUAL),
        }


ControlOtrosGastosCruceServiceDependency = Annotated[
    ControlOtrosGastosCruceService, Depends()
]


@dataclass
# -------------------------------------------------
class ControlOtrosGastosExportService:
    """Export UNIFICADO de Otros Gastos: una sola ruta
    (``GET /control/otrosGastos/export``) sube un único Google Sheet
    con las 4 hojas (SIIF, SGF y los 2 cruces).

    Prioriza el snapshot persistido de cada tabla (POST posterior a
    ``/generate``) y cae al cómputo on-demand si el snapshot está vacío.
    """

    siif_service: ControlOtrosGastosSiifServiceDependency
    sgf_service: ControlOtrosGastosSgfServiceDependency
    cruce_service: ControlOtrosGastosCruceServiceDependency

    # -------------------------------------------------
    async def export(self, params: ControlOtrosGastosExportFilter) -> dict[str, Any]:
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
                f"hojas: {HOJA_SIIF}, {HOJA_SGF}, {HOJA_CRUCE_RESTO} y "
                f"{HOJA_CRUCE_FONDOS_PERM}."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_OTROS_GASTOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlOtrosGastosExportFilter
    ) -> None:
        """Tarea de fondo: sube las 4 hojas a UN único Google Sheet.

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

                # Cruce (Capa 1: pareos + Capa 2: mensual): snapshot
                # con fallback al cómputo on-demand.
                bloque = await self.cruce_service.get_snapshot(
                    params=ControlOtrosGastosCruceFilter(
                        ejercicio=params.ejercicio,
                        limit=None,
                    )
                )
                if not bloque["pareos"] and not bloque["mensual"]:
                    bloque = await self.cruce_service.generate(
                        params=ControlOtrosGastosCruceGenerateFilter(
                            ejercicio=params.ejercicio
                        )
                    )
                df_pareos = pd.DataFrame(bloque["pareos"])
                df_mensual = pd.DataFrame(bloque["mensual"])

                # 2. Una sola suba: las 4 hojas al mismo key,
                #    descartando las hojas vacías
                sheets = []
                if not df_siif.empty:
                    sheets.append((df_siif, HOJA_SIIF))
                if not df_sgf.empty:
                    sheets.append((df_sgf, HOJA_SGF))
                if not df_pareos.empty:
                    sheets.append((df_pareos, HOJA_CRUCE_RESTO))
                if not df_mensual.empty:
                    sheets.append((df_mensual, HOJA_CRUCE_FONDOS_PERM))

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
