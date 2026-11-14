__all__ = ["ControlEscribanosService", "ControlEscribanosServiceDependency"]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...siif.schemas import Rcocc31FullFilter
from ...siif.services import Rcocc31ServiceDependency
from ...sscc.schemas import BancoINVICOFullFilter
from ...sscc.services import BancoINVICOServiceDependency, CtasCtesServiceDependency
from ...utils import (
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories.control_escribanos import (
    ControlEscribanosSGFvsSSCCRepositoryDependency,
    ControlEscribanosSIIFvsSGFRepositoryDependency,
)
from ..schemas.control_escribanos import (
    ControlEscribanosFullFilter,
    ControlEscribanosGenerateFilter,
    ControlEscribanosLiteFilter,
    ControlEscribanosSGFvsSSCCReport,
    ControlEscribanosSIIFvsSGFReport,
)

SPREADSHEET_KEY_CONTROL_ESCRIBANOS: str = "1Tz3uvUGBL8ZDSFsYRBP8hgIis-hlhs_sQ6V5bI4LaTg"

# Cta. contable SIIF de Escribanos (FEI / PFE)
CTA_CONTABLE_ESCRIBANOS: str = "2113-2-9"
# Cta. cte. de Escribanos en SGF y en el banco (nexo Ctas Ctes)
CTA_CTE_ESCRIBANOS: str = "130832-08"
# Imputaciones del banco que no corresponden al pago de Escribanos
COD_IMPUTACION_EXCLUIDAS: List[str] = ["004", "034", "213", "102"]

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlEscribanosService:
    control_siif_vs_sgf_repository: ControlEscribanosSIIFvsSGFRepositoryDependency
    control_sgf_vs_sscc_repository: ControlEscribanosSGFvsSSCCRepositoryDependency
    rcocc31_service: Rcocc31ServiceDependency
    sgf_service: ResumenRendProvServiceDependency
    banco_service: BancoINVICOServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def add_many_siif_vs_sgf(
        self, data: List[ControlEscribanosSIIFvsSGFReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce SIIF vs SGF con borrado idempotente por
        ejercicio (patrón generate -> POST de los demás controles)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlEscribanosSIIFvsSGFReport,
                field_id=["ejercicio", "mes", "cuit"],  # Clave de la fila
            )

            delete_filter = {}
            if validation_result.validated:
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.control_siif_vs_sgf_repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Escribanos SIIF vs SGF",
                label="Control Escribanos SIIF vs SGF",
                logger=logger,
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def add_many_sgf_vs_sscc(
        self, data: List[ControlEscribanosSGFvsSSCCReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce SGF vs SSCC con borrado idempotente por
        ejercicio (patrón generate -> POST de los demás controles)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlEscribanosSGFvsSSCCReport,
                field_id=["ejercicio", "mes"],  # Clave de la fila
            )

            delete_filter = {}
            if validation_result.validated:
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.control_sgf_vs_sscc_repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Escribanos SGF vs SSCC",
                label="Control Escribanos SGF vs SSCC",
                logger=logger,
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate_siif_vs_sgf(
        self, params: ControlEscribanosGenerateFilter
    ) -> List[ControlEscribanosSIIFvsSGFReport]:
        """Cruce SIIF vs SGF on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlEscribanosFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_siif_vs_sgf(params=compute_params)

    # -------------------------------------------------
    async def generate_sgf_vs_sscc(
        self, params: ControlEscribanosGenerateFilter
    ) -> List[ControlEscribanosSGFvsSSCCReport]:
        """Cruce SGF vs SSCC on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlEscribanosFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_sgf_vs_sscc(params=compute_params)

    # -------------------------------------------------
    async def get_snapshot_siif_vs_sgf(
        self, params: ControlEscribanosFullFilter
    ) -> List[ControlEscribanosSIIFvsSGFReport]:
        """Lee el snapshot persistido del cruce SIIF vs SGF."""
        return await self.control_siif_vs_sgf_repository.find_with_filter_params(
            params=params
        )

    # -------------------------------------------------
    async def get_snapshot_sgf_vs_sscc(
        self, params: ControlEscribanosFullFilter
    ) -> List[ControlEscribanosSGFvsSSCCReport]:
        """Lee el snapshot persistido del cruce SGF vs SSCC."""
        return await self.control_sgf_vs_sscc_repository.find_with_filter_params(
            params=params
        )

    # -------------------------------------------------
    async def delete_siif_vs_sgf(self, params: ControlEscribanosLiteFilter) -> dict:
        """Borra el snapshot SIIF vs SGF según el filtro (sin límite)."""
        try:
            full_filter = ControlEscribanosFullFilter(
                **params.model_dump(exclude_none=True),
                limit=None,
            )
            deleted_count = (
                await self.control_siif_vs_sgf_repository.delete_with_filter_params(
                    params=full_filter
                )
            )
            return {
                "title": "Proceso de eliminación Control Escribanos SIIF vs SGF",
                "deleted": deleted_count,
                "added": 0,
                "errors": [],
            }
        except Exception as e:
            self._handle_error("Error en eliminación SIIF vs SGF", e)

    # -------------------------------------------------
    async def delete_sgf_vs_sscc(self, params: ControlEscribanosLiteFilter) -> dict:
        """Borra el snapshot SGF vs SSCC según el filtro (sin límite)."""
        try:
            full_filter = ControlEscribanosFullFilter(
                **params.model_dump(exclude_none=True),
                limit=None,
            )
            deleted_count = (
                await self.control_sgf_vs_sscc_repository.delete_with_filter_params(
                    params=full_filter
                )
            )
            return {
                "title": "Proceso de eliminación Control Escribanos SGF vs SSCC",
                "deleted": deleted_count,
                "added": 0,
                "errors": [],
            }
        except Exception as e:
            self._handle_error("Error en eliminación SGF vs SSCC", e)

    # -------------------------------------------------
    async def _siif_escribanos_df(self, ejercicio: int) -> pd.DataFrame:
        """SIIF rcocc31 (cta. contable 2113-2-9) del ejercicio sin APE.

        Renombra ``auxiliar_1`` a ``cuit``, ``creditos`` a ``carga_fei``
        y ``debitos`` a ``pagos_fei``; agrega ``fei_impagos`` y
        normaliza el CUIT a 11 dígitos (si no, queda ``00000000000``),
        igual que el script original de invicofapy.

        Returns:
            DataFrame crudo del SIIF (vacío si no hay datos).
        """
        siif_params = Rcocc31FullFilter(
            ejercicio=str(ejercicio),
            cta_contable=CTA_CONTABLE_ESCRIBANOS,
            limit=None,  # Para traer todo
        )
        siif_params.set_extra_filter({"tipo_comprobante": {"$ne": "APE"}})
        data = await self.rcocc31_service.get_all(params=siif_params)
        df = self._to_df(data=[document.model_dump(by_alias=True) for document in data])
        if df.empty:
            return df
        df = df.rename(
            columns={
                "auxiliar_1": "cuit",
                "creditos": "carga_fei",
                "debitos": "pagos_fei",
            }
        )
        df["fei_impagos"] = df["carga_fei"] - df["pagos_fei"]
        df["cuit"] = np.where(
            df["cuit"].astype(str).str.len() == 11, df["cuit"], "00000000000"
        )
        return df

    # -------------------------------------------------
    async def _sgf_escribanos_df(self, ejercicio: int) -> pd.DataFrame:
        """SGF Resumen de Rendiciones Proveedores de la cta. cte.
        130832-08 (Escribanos) del ejercicio.

        Returns:
            DataFrame crudo del SGF (vacío si no hay datos).
        """
        sgf_params = ResumenRendProvFullFilter(
            ejercicio=str(ejercicio),
            limit=None,  # Para traer todo
        )
        sgf_params.set_extra_filter({"cta_cte": CTA_CTE_ESCRIBANOS})
        data = await self.sgf_service.get_all(params=sgf_params)
        return self._to_df(
            data=[document.model_dump(by_alias=True) for document in data]
        )

    # -------------------------------------------------
    async def _sscc_escribanos_df(self, ejercicio: int) -> pd.DataFrame:
        """SSCC Resumen General de Movimientos unido con Ctas Ctes
        (nexo ``sscc_cta_cte``), filtrado por la cta. cte. 130832-08 y
        sin las imputaciones excluidas.

        Returns:
            DataFrame crudo del banco (vacío si no hay datos).
        """
        banco_params = BancoINVICOFullFilter(
            ejercicio=str(ejercicio),
            limit=None,  # Para traer todo
        )
        data = await self.banco_service.get_all(params=banco_params)
        df = self._to_df(data=[document.model_dump(by_alias=True) for document in data])
        if df.empty:
            return df
        df = await self.cta_cte_service.cta_cte_unifier(df, "sscc_cta_cte")
        df = df.loc[
            (df["cta_cte"] == CTA_CTE_ESCRIBANOS)
            & (~df["cod_imputacion"].isin(COD_IMPUTACION_EXCLUIDAS))
        ]
        return df.reset_index(drop=True)

    # -------------------------------------------------
    async def get_siif_escribanos(
        self, params: ControlEscribanosFullFilter
    ) -> list[dict]:
        """Crudo SIIF rcocc31 (2113-2-9) para la hoja ``siif_db``."""
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio.",
            )
        df = await self._siif_escribanos_df(ejercicio=params.ejercicio)
        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def get_sgf_escribanos(
        self, params: ControlEscribanosFullFilter
    ) -> list[dict]:
        """Crudo SGF (130832-08) para la hoja ``sgf_db``."""
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio.",
            )
        df = await self._sgf_escribanos_df(ejercicio=params.ejercicio)
        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def get_sscc_escribanos(
        self, params: ControlEscribanosFullFilter
    ) -> list[dict]:
        """Crudo SSCC banco unificado para la hoja ``sscc_db``."""
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio.",
            )
        df = await self._sscc_escribanos_df(ejercicio=params.ejercicio)
        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def siif_summarize(
        self,
        ejercicio: int,
        groupby_cols: List[str] = ["ejercicio", "mes", "cuit"],
    ) -> pd.DataFrame:
        """Resumen SIIF (carga/pagos FEI) agrupado por ``groupby_cols``.

        Args:
            ejercicio: Ejercicio a resumir.
            groupby_cols: Columnas de agrupación.

        Returns:
            DataFrame con los totales de ``carga_fei``, ``pagos_fei`` y
            ``fei_impagos`` (con columnas sintéticas vacías si el SIIF
            aún no tiene datos de ese ejercicio).
        """
        value_cols = ["carga_fei", "pagos_fei", "fei_impagos"]
        df = await self._siif_escribanos_df(ejercicio=ejercicio)
        if df.empty or not set(groupby_cols).issubset(df.columns):
            return pd.DataFrame(columns=groupby_cols + value_cols)
        df = df.drop(
            columns=[
                "tipo_comprobante",
                "fecha",
                "fecha_aprobado",
                "cta_contable",
                "auxiliar_2",
                "saldo",
                "nro_entrada",
                "nro_original",
            ],
            errors="ignore",
        )
        df = df.groupby(groupby_cols).sum(numeric_only=True)
        df = df.reset_index()
        df = df.fillna(0)
        return df

    # -------------------------------------------------
    async def sgf_summarize(
        self,
        ejercicio: int,
        groupby_cols: List[str] = ["ejercicio", "mes", "cuit", "beneficiario"],
    ) -> pd.DataFrame:
        """Resumen SGF (importe neto) agrupado por ``groupby_cols``.

        Args:
            ejercicio: Ejercicio a resumir.
            groupby_cols: Columnas de agrupación.

        Returns:
            DataFrame con ``importe_neto`` total (con columnas sintéticas
            vacías si el SGF aún no tiene datos de ese ejercicio).
        """
        value_cols = ["importe_neto"]
        df = await self._sgf_escribanos_df(ejercicio=ejercicio)
        if df.empty or not set(groupby_cols).issubset(df.columns):
            return pd.DataFrame(columns=groupby_cols + value_cols)
        df = df.drop(
            columns=[
                "origen",
                "fecha",
                "destino",
                "libramiento",
                "seguro",
                "salud",
                "mutual",
                "otras",
                "importe_bruto",
                "gcias",
                "iibb",
                "sellos",
                "suss",
                "invico",
                "retenciones",
                "movimiento",
                "cta_cte",
            ],
            errors="ignore",
        )
        # Rellena los valores nulos solo en la columna específica
        if "cuit" in df.columns:
            df["cuit"] = df["cuit"].fillna("0")
        df = df.groupby(groupby_cols).sum(numeric_only=True)
        df = df.reset_index()
        return df

    # -------------------------------------------------
    async def sscc_summarize(
        self,
        ejercicio: int,
        groupby_cols: List[str] = ["ejercicio", "mes", "cod_imputacion", "imputacion"],
    ) -> pd.DataFrame:
        """Resumen SSCC (importe neto, signo invertido) agrupado por
        ``groupby_cols``.

        Args:
            ejercicio: Ejercicio a resumir.
            groupby_cols: Columnas de agrupación.

        Returns:
            DataFrame con ``importe_neto`` total (positivo = pago) con
            columnas sintéticas vacías si el banco aún no tiene datos.
        """
        value_cols = ["importe_neto"]
        df = await self._sscc_escribanos_df(ejercicio=ejercicio)
        if df.empty or not set(groupby_cols).issubset(df.columns):
            return pd.DataFrame(columns=groupby_cols + value_cols)
        df = df.drop(columns=["es_cheque"], errors="ignore")
        df = df.groupby(groupby_cols).sum(numeric_only=True)
        df = df.reset_index()
        df["importe"] = df["importe"] * -1
        df = df.rename(columns={"importe": "importe_neto"})
        return df

    # -------------------------------------------------
    async def compute_control_siif_vs_sgf(
        self,
        params: ControlEscribanosFullFilter,
        only_diff: bool = False,
    ) -> List[dict]:
        """Cruce Escribanos SIIF vs SGF on-demand (sin persistir).

        Replica el cómputo del script original de invicofapy: resúmenes
        por ``[ejercicio, mes, cuit]`` del rcocc31 (2113-2-9) y de las
        rendiciones del SGF (130832-08), con ``dif_pagos = pagos_fei -
        pagos_sgf``. Los lados vacíos se rellenan con columnas
        sintéticas para que el ``merge`` no truenen cuando todavía no
        hay datos crudos de un sistema.

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.
            only_diff: Si es True, devuelve solo las filas con
                diferencia material (``|suma| > 0.01``).

        Returns:
            Filas del cruce como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio = params.ejercicio
        groupby_cols = ["ejercicio", "mes", "cuit"]

        siif = await self.siif_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        sgf = await self.sgf_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        sgf = sgf.rename(columns={"importe_neto": "pagos_sgf"})

        # 🔹 Merge completo (outer join) por índice
        siif = siif.set_index(groupby_cols)
        sgf = sgf.set_index(groupby_cols)
        df = siif.merge(sgf, how="outer", left_index=True, right_index=True)
        df = df.reset_index()
        df = df.fillna(0)
        df["dif_pagos"] = df["pagos_fei"] - df["pagos_sgf"]

        if only_diff:
            numeric_cols = df.select_dtypes(include=np.number).columns.drop("ejercicio")
            df = df[np.abs(df[numeric_cols].sum(axis=1)) > 0.01]
            df = df.reset_index(drop=True)

        if df.empty:
            return []

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_sgf_vs_sscc(
        self,
        params: ControlEscribanosFullFilter,
        only_diff: bool = True,
    ) -> List[dict]:
        """Cruce Escribanos SGF vs SSCC on-demand (sin persistir).

        Replica el cómputo del script original de invicofapy: resúmenes
        por ``[ejercicio, mes]`` de las rendiciones del SGF (130832-08)
        y de los pagos del banco (sin imputaciones excluidas), con
        ``dif_importe_neto = sgf_importe_neto - sscc_importe_neto``.

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.
            only_diff: Si es True (default), devuelve solo las filas con
                diferencia material (``|dif| > 0.01``).

        Returns:
            Filas del cruce como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio = params.ejercicio
        groupby_cols = ["ejercicio", "mes"]

        sgf = await self.sgf_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        sgf = sgf.rename(columns={"importe_neto": "sgf_importe_neto"})
        sscc = await self.sscc_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        sscc = sscc.rename(columns={"importe_neto": "sscc_importe_neto"})

        # 🔹 Merge completo (outer join) por índice
        sgf = sgf.set_index(groupby_cols)
        sscc = sscc.set_index(groupby_cols)
        df = sgf.merge(sscc, how="outer", left_index=True, right_index=True)
        df = df.reset_index()
        df = df.fillna(0)
        df["dif_importe_neto"] = df["sgf_importe_neto"] - df["sscc_importe_neto"]

        if only_diff:
            df = df[np.abs(df["dif_importe_neto"]) > 0.01]
            df = df.reset_index(drop=True)

        if df.empty:
            return []

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(
        self, params: ControlEscribanosLiteFilter, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        El trabajo pesado (queries de los crudos, cruces con fallback y
        upload de las 5 hojas) corre como tarea de fondo para no
        bloquear el event loop ni agotar el timeout de Koyeb. NO se
        genera el archivo Excel: la subida a Google Sheets es el único
        destino de la exportación (patrón ``control_honorarios``).

        Raises:
            HTTPException: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio para exportar.",
            )
        background_tasks.add_task(self._export_to_google_sheets, params)
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "siif_vs_sgf_db, sgf_vs_sscc_db, siif_db, sscc_db y sgf_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_ESCRIBANOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlEscribanosLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        NO genera el archivo Excel: solo queries + upload, corriendo
        fuera del request. Procesa de a una hoja para mantener el pico
        de memoria acotado (Koyeb dispone de poca RAM en su capa
        gratuita).

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlEscribanosFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Cruces desde los snapshots persistidos; si todavía no
            #    existen, se calculan on-demand para no dejar la hoja
            #    vacía (mismo criterio que control_honorarios).
            snapshot_siif_vs_sgf = await self.get_snapshot_siif_vs_sgf(
                params=search_params
            )
            data_siif_vs_sgf = (
                [doc.model_dump(by_alias=True) for doc in snapshot_siif_vs_sgf]
                if snapshot_siif_vs_sgf
                else await self.compute_control_siif_vs_sgf(
                    params=search_params, only_diff=False
                )
            )
            snapshot_sgf_vs_sscc = await self.get_snapshot_sgf_vs_sscc(
                params=search_params
            )
            data_sgf_vs_sscc = (
                [doc.model_dump(by_alias=True) for doc in snapshot_sgf_vs_sscc]
                if snapshot_sgf_vs_sscc
                else await self.compute_control_sgf_vs_sscc(
                    params=search_params, only_diff=True
                )
            )

            # 2. Crudos (servicios async)
            data_siif = await self.get_siif_escribanos(params=search_params)
            data_sgf = await self.get_sgf_escribanos(params=search_params)
            data_sscc = await self.get_sscc_escribanos(params=search_params)

            # 3. Upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[list[dict], str]] = [
                (data_siif_vs_sgf, "siif_vs_sgf_db_new"),
                (data_sgf_vs_sscc, "sgf_vs_sscc_db_new"),
                (data_siif, "siif_db_new"),
                (data_sscc, "sscc_db_new"),
                (data_sgf, "sgf_db_new"),
            ]
            for records, sheet_name in sheets:
                try:
                    # DataFrame + sanitizado + upload corren en el threadpool
                    await run_in_threadpool(
                        self._build_df_and_upload, records, sheet_name
                    )
                    logger.info(
                        f"Control Escribanos: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Escribanos: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info("Control Escribanos: exportación a Google Sheets finalizada")

    # -------------------------------------------------
    @staticmethod
    def _build_df_and_upload(records: list[dict], sheet_name: str) -> None:
        """Construye el DataFrame y sube la hoja (bloqueante → threadpool).

        Descarta los id internos de Mongo y NO genera el archivo Excel:
        solo sube la hoja a Google Sheets.
        """
        df = pd.DataFrame(records).drop(columns=["id", "_id"], errors="ignore")
        upload_multiple_dataframes_to_google_sheets(
            [(df, sheet_name)],
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_ESCRIBANOS,
        )

    # -------------------------------------------------
    def _handle_error(
        self, message: str, exception: Exception, status_code: int = 500
    ) -> None:
        """Registra el error y lo re-lanza como ``HTTPException``.

        Mismo criterio de ``BaseService._handle_error``: nunca se traga
        la excepción (log + raise), para que la capa de rutas la convierta
        en una respuesta HTTP clara.
        """
        logger.error(f"{message}: {exception}")
        raise HTTPException(
            status_code=status_code,
            detail=f"{message}: {str(exception)}",
        )

    # -------------------------------------------------
    def _finalize(self, df: pd.DataFrame, params) -> list[dict]:
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)
        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    @staticmethod
    def _to_df(data: list, columns: list[str] | None = None) -> pd.DataFrame:
        df = (
            pd.DataFrame(data, columns=columns)
            if data
            else pd.DataFrame(columns=columns)
        )
        return df.drop(columns=["id", "_id"], errors="ignore")


ControlEscribanosServiceDependency = Annotated[ControlEscribanosService, Depends()]
