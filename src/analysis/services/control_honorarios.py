__all__ = [
    "ControlHonorariosService",
    "ControlHonorariosServiceDependency",
]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import BackgroundTasks, Depends
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...siif.schemas import GtoRpa03gFullFilter
from ...siif.services import (
    GtoRpa03gServiceDependency,
)
from ...slave.schemas import HonorariosFullFilter
from ...slave.services import HonorariosServiceDependency
from ...sscc.schemas import BancoINVICOFullFilter
from ...sscc.services import BancoINVICOServiceDependency, CtasCtesServiceDependency
from ...utils import (
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories import (
    ControlHonorariosSGFvsSlaveRepositoryDependency,
    ControlHonorariosSIIFvsSlaveRepositoryDependency,
)
from ..schemas import (
    ControlHonorariosFullFilter,
    ControlHonorariosGenerateFilter,
    ControlHonorariosLiteFilter,
    ControlHonorariosSGFvsSlaveReport,
    ControlHonorariosSIIFvsSlaveReport,
)

SPREADSHEET_KEY_CONTROL_HONORARIOS: str = "1fQhp1CdESnvqzrp3QMV5bFSHmGdi7SNoaBRWtmw-JgA"

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlHonorariosService:
    siif_vs_slave_repository: ControlHonorariosSIIFvsSlaveRepositoryDependency
    sgf_vs_slave_repository: ControlHonorariosSGFvsSlaveRepositoryDependency
    gastos_service: GtoRpa03gServiceDependency
    slave_service: HonorariosServiceDependency
    sgf_service: ResumenRendProvServiceDependency
    banco_service: BancoINVICOServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def add_many_siif_vs_slave(
        self, data: List[ControlHonorariosSIIFvsSlaveReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce SIIF vs Slave con borrado idempotente por
        ejercicio (patrón generate -> POST de los demás controles)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlHonorariosSIIFvsSlaveReport,
                field_id=["ejercicio", "siif_nro"],  # Clave de la fila
            )

            delete_filter = {}
            if validation_result.validated:
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.siif_vs_slave_repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Honorarios SIIF vs Slave",
                label="Control Honorarios SIIF vs Slave",
                logger=logger,
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def add_many_sgf_vs_slave(
        self, data: List[ControlHonorariosSGFvsSlaveReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce SGF vs Slave con borrado idempotente por
        ejercicio (patrón generate -> POST de los demás controles)."""
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlHonorariosSGFvsSlaveReport,
                field_id=["ejercicio", "mes", "cta_cte", "beneficiario"],
            )

            delete_filter = {}
            if validation_result.validated:
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.sgf_vs_slave_repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Honorarios SGF vs Slave",
                label="Control Honorarios SGF vs Slave",
                logger=logger,
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate_siif_vs_slave(
        self, params: ControlHonorariosGenerateFilter
    ) -> List[ControlHonorariosSIIFvsSlaveReport]:
        """Cruce SIIF vs Slave on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlHonorariosFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_siif_vs_slave(params=compute_params)

    # -------------------------------------------------
    async def generate_sgf_vs_slave(
        self, params: ControlHonorariosGenerateFilter
    ) -> List[ControlHonorariosSGFvsSlaveReport]:
        """Cruce SGF vs Slave on-demand (sin persistir; el snapshot lo
        congela el POST posterior).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlHonorariosFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_sgf_vs_slave(params=compute_params)

    # -------------------------------------------------
    async def get_snapshot_siif_vs_slave(
        self, params: ControlHonorariosFullFilter
    ) -> List[ControlHonorariosSIIFvsSlaveReport]:
        """Lee el snapshot persistido del cruce SIIF vs Slave."""
        return await self.siif_vs_slave_repository.find_with_filter_params(
            params=params
        )

    # -------------------------------------------------
    async def get_snapshot_sgf_vs_slave(
        self, params: ControlHonorariosFullFilter
    ) -> List[ControlHonorariosSGFvsSlaveReport]:
        """Lee el snapshot persistido del cruce SGF vs Slave."""
        return await self.sgf_vs_slave_repository.find_with_filter_params(params=params)

    # -------------------------------------------------
    async def delete_siif_vs_slave(self, params: ControlHonorariosLiteFilter) -> dict:
        """Borra el snapshot SIIF vs Slave según el filtro (sin límite)."""
        try:
            full_filter = ControlHonorariosFullFilter(
                **params.model_dump(exclude_none=True),
                limit=None,
            )
            deleted_count = (
                await self.siif_vs_slave_repository.delete_with_filter_params(
                    params=full_filter
                )
            )
            return {
                "title": "Proceso de eliminación Control Honorarios SIIF vs Slave",
                "deleted": deleted_count,
                "added": 0,
                "errors": [],
            }
        except Exception as e:
            self._handle_error("Error en eliminación SIIF vs Slave", e)

    # -------------------------------------------------
    async def delete_sgf_vs_slave(self, params: ControlHonorariosLiteFilter) -> dict:
        """Borra el snapshot SGF vs Slave según el filtro (sin límite)."""
        try:
            full_filter = ControlHonorariosFullFilter(
                **params.model_dump(exclude_none=True),
                limit=None,
            )
            deleted_count = (
                await self.sgf_vs_slave_repository.delete_with_filter_params(
                    params=full_filter
                )
            )
            return {
                "title": "Proceso de eliminación Control Honorarios SGF vs Slave",
                "deleted": deleted_count,
                "added": 0,
                "errors": [],
            }
        except Exception as e:
            self._handle_error("Error en eliminación SGF vs Slave", e)

    # -------------------------------------------------
    async def get_siif_honorarios(
        self,
        params: ControlHonorariosFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            query_filter="partida!=str:384, grupo=str:3",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.gastos_service.get_joined_with_rcg01_uejp(
            params=gastos_params
        )
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = self._to_df(data=data)

        # 2. Filtramos el DataFrame
        df = df.loc[df["cuit"] == "30632351514"]
        df = df.loc[df["cta_cte"].isin(["130832-05", "130832-07"])]
        keep = ["HONOR", "RECON", "LOC"]
        df = df.loc[df.glosa.str.contains("|".join(keep), na=False, case=False)]

        df["grupo"] = df["grupo"] + "00"
        df = df.loc[
            :,
            [
                "ejercicio",
                "mes",
                "fecha",
                "nro_comprobante",
                "importe",
                "grupo",
                "partida",
                "nro_entrada",
                "nro_origen",
                "nro_expte",
                "glosa",
                "beneficiario",
                "nro_fondo",
                "fuente",
                "cta_cte",
                "cuit",
                "clase_reg",
                "clase_mod",
                "clase_gto",
                "es_comprometido",
                "es_verificado",
                "es_aprobado",
                "es_pagado",
            ],
        ]

        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def get_slave_honorarios(
        self,
        params: ControlHonorariosFullFilter,
        siif: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        slave_params = HonorariosFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.slave_service.get_all(params=slave_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = self._to_df(data=[d.model_dump(by_alias=True) for d in data])

        # 2. Renombramos columnas
        df = df.rename(
            columns={
                "nombre_completo": "beneficiario",
            }
        )

        # 3. Convertimos las columnas numéricas a tipo numérico y rellenamos NaN con 0
        num_cols = [
            "importe_bruto",
            "iibb",
            "lp",
            "sellos",
            "seguro",
            "otras_retenciones",
            "anticipo",
            "descuento",
            "mutual",
            "embargo",
        ]
        df[num_cols] = df[num_cols].fillna(0).apply(pd.to_numeric, errors="coerce")

        # 4. Unificamos campo cta_cte
        df = await self.cta_cte_service.cta_cte_unifier(df, "icaro_cta_cte")

        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def get_sgf_honorarios(
        self,
        params: ControlHonorariosFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        sgf_params = ResumenRendProvFullFilter(
            query_filter="origen!=OBRAS",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        sgf_params.set_extra_filter(
            {
                "destino": {
                    "$in": [
                        "HONORARIOS - FUNCIONAMIENTO",
                        "COMISIONES - FUNCIONAMIENTO",
                        "HONORARIOS - EPAM",
                    ]
                },
                "cta_cte": {
                    "$in": [
                        "130832-05",
                        "130832-07",
                    ]
                },
            }
        )

        data = await self.sgf_service.drop_duplicates_optimizado(params=sgf_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = self._to_df(data=data)

        # 2. Depuramos embargos en la cta_cte 130832-05
        banco_params = BancoINVICOFullFilter(
            query_filter="cta_cte=130832-05, cod_imputacion=str:049",
            ejercicio=str(params.ejercicio),
            limit=None,
        )
        banco = await self.banco_service.get_all(params=banco_params)
        if banco:
            banco = pd.DataFrame([d.model_dump(by_alias=True) for d in banco])
            banco["importe_bruto"] = banco["importe"] * (-1)
            banco["importe_neto"] = 0
            banco["otras"] = banco["importe_bruto"]
            banco["retenciones"] = banco["importe_bruto"]
            banco["origen"] = "BANCO"
            banco["destino"] = "EMBARGO POR ALIMENTOS"
            banco["beneficiario"] = "EMBARGO POR ALIMENTOS"
            # banco.rename(
            #     columns={
            #         "libramiento": "libramiento_sgf",
            #     },
            #     inplace=True,
            # )
            banco = banco.loc[
                :,
                [
                    "ejercicio",
                    "mes",
                    "fecha",
                    "beneficiario",
                    "destino",
                    "cta_cte",
                    "libramiento",
                    "movimiento",
                    "importe_bruto",
                    "otras",
                    "retenciones",
                    "importe_neto",
                ],
            ]
            df = pd.concat([df, banco])
            num_cols = [
                "importe_bruto",
                "otras",
                "retenciones",
                "importe_neto",
            ]
            df[num_cols] = df[num_cols].fillna(0).apply(pd.to_numeric, errors="coerce")

        return self._finalize(df=df, params=params)

    # -------------------------------------------------
    async def compute_control_siif_vs_slave(
        self,
        params: ControlHonorariosFullFilter,
        siif: list[dict] = None,
        slave: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "mes", "nro_comprobante"]

        if siif is None:
            siif = await self.get_siif_honorarios(params=params)
        siif = pd.DataFrame(siif)
        siif = siif.loc[:, groupby_cols + ["importe"]]
        siif = siif.groupby(groupby_cols)["importe"].sum()
        siif = siif.reset_index()
        siif = siif.rename(
            columns={
                "importe": "siif_importe",
                "nro_comprobante": "siif_nro",
                "mes": "siif_mes",
            }
        )
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if slave is None:
            slave = await self.get_slave_honorarios(params=params)
        slave = pd.DataFrame(slave)
        slave = slave.loc[:, groupby_cols + ["importe_bruto"]]
        slave = slave.groupby(groupby_cols)["importe_bruto"].sum()
        slave = slave.reset_index()
        slave = slave.rename(
            columns={
                "importe_bruto": "slave_importe",
                "nro_comprobante": "slave_nro",
                "mes": "slave_mes",
            }
        )
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(
            siif,
            slave,
            how="outer",
            left_on=["ejercicio", "siif_nro"],
            right_on=["ejercicio", "slave_nro"],
            copy=False,
        )
        num_cols = ["siif_importe", "slave_importe"]
        df[num_cols] = df[num_cols].fillna(0).apply(pd.to_numeric, errors="coerce")
        df["err_nro"] = df["siif_nro"] != df["slave_nro"]
        df["err_importe"] = np.where(
            np.abs(df["siif_importe"] - df["slave_importe"]) > 0.01, True, False
        )
        df["err_mes"] = df["siif_mes"] != df["slave_mes"]
        df = df.loc[
            :,
            [
                "ejercicio",
                "siif_nro",
                "slave_nro",
                "err_nro",
                "siif_importe",
                "slave_importe",
                "err_importe",
                "siif_mes",
                "slave_mes",
                "err_mes",
            ],
        ]
        # print(f"df.shape: {df.shape} - df.head: {df.head()}")
        df = df.query("err_nro | err_mes | err_importe")
        df = df.sort_values(by=["err_nro", "err_importe", "err_mes"], ascending=False)
        df = df.reset_index(drop=True)

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_sgf_vs_slave(
        self,
        params: ControlHonorariosFullFilter,
        sgf: list[dict] = None,
        slave: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "mes", "cta_cte", "beneficiario"]

        if sgf is None:
            sgf = await self.get_sgf_honorarios(params=params)
        sgf = pd.DataFrame(sgf)
        sgf = sgf.loc[:, groupby_cols + ["importe_bruto", "importe_neto"]]
        sgf = sgf.groupby(groupby_cols)[["importe_bruto", "importe_neto"]].sum()
        sgf = sgf.reset_index()
        sgf = sgf.rename(
            columns={
                "importe_bruto": "sgf_importe_bruto",
                "importe_neto": "sgf_importe_neto",
            }
        )
        # print(f"sgf.shape: {sgf.shape} - sgf.head: {sgf.head()}")

        if slave is None:
            slave = await self.get_slave_honorarios(params=params)
        slave = pd.DataFrame(slave)
        slave["importe_neto"] = (
            slave["importe_bruto"]
            - slave["iibb"]
            - slave["lp"]
            - slave["sellos"]
            - slave["seguro"]
            - slave["otras_retenciones"]
            - slave["anticipo"]
            - slave["descuento"]
            - slave["mutual"]
            - slave["embargo"]
        )
        slave = slave.loc[:, groupby_cols + ["importe_bruto", "importe_neto"]]
        slave = slave.groupby(groupby_cols)[["importe_bruto", "importe_neto"]].sum()
        slave = slave.reset_index()
        slave = slave.rename(
            columns={
                "importe_bruto": "slave_importe_bruto",
                "importe_neto": "slave_importe_neto",
            }
        )
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(
            sgf,
            slave,
            how="outer",
            on=groupby_cols,
            copy=False,
        )
        num_cols = [
            "sgf_importe_bruto",
            "sgf_importe_neto",
            "slave_importe_bruto",
            "slave_importe_neto",
        ]
        df[num_cols] = df[num_cols].fillna(0).apply(pd.to_numeric, errors="coerce")
        df["dif_importe_bruto"] = df["sgf_importe_bruto"] - df["slave_importe_bruto"]
        df["dif_importe_neto"] = df["sgf_importe_neto"] - df["slave_importe_neto"]
        df = df.loc[
            :,
            groupby_cols
            + [
                "sgf_importe_bruto",
                "slave_importe_bruto",
                "dif_importe_bruto",
                "sgf_importe_neto",
                "slave_importe_neto",
                "dif_importe_neto",
            ],
        ]
        # print(f"df.shape: {df.shape} - df.head: {df.head()}")
        df = df.query("abs(dif_importe_bruto) > 0.01 | abs(dif_importe_neto) > 0.01")
        df = df.sort_values(by=groupby_cols, ascending=True)
        df = df.reset_index(drop=True)

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(
        self, params: ControlHonorariosLiteFilter, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        El trabajo pesado (queries de los crudos, cruces con fallback y
        upload de las 5 hojas) corre como tarea de fondo para no
        bloquear el event loop ni agotar el timeout de Koyeb. No se
        genera el archivo Excel: la subida a Google Sheets es el único
        destino de la exportación (patrón ``control_banco``).
        """
        background_tasks.add_task(self._export_to_google_sheets, params)
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "siif_vs_slave_db, sgf_vs_slave_db, siif_db, slave_db y sgf_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_HONORARIOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlHonorariosLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        NO genera el archivo Excel (a diferencia del export binario
        anterior): solo queries + upload, corriendo fuera del request.
        Procesa de a una hoja para mantener el pico de memoria acotado
        (Koyeb dispone de poca RAM en su capa gratuita).

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlHonorariosFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Crudos (servicios async)
            data_siif = await self.get_siif_honorarios(params=search_params)
            data_slave = await self.get_slave_honorarios(
                params=search_params, siif=data_siif
            )
            data_sgf = await self.get_sgf_honorarios(params=search_params)

            # 2. Cruces desde los snapshots persistidos; si todavía no
            #    existen, se calculan on-demand para no dejar la hoja
            #    vacía (mismo criterio que el export binario anterior).
            snapshot_siif_vs_slave = await self.get_snapshot_siif_vs_slave(
                params=search_params
            )
            data_siif_vs_slave = (
                [doc.model_dump(by_alias=True) for doc in snapshot_siif_vs_slave]
                if snapshot_siif_vs_slave
                else await self.compute_control_siif_vs_slave(
                    params=search_params, siif=data_siif, slave=data_slave
                )
            )
            snapshot_sgf_vs_slave = await self.get_snapshot_sgf_vs_slave(
                params=search_params
            )
            data_sgf_vs_slave = (
                [doc.model_dump(by_alias=True) for doc in snapshot_sgf_vs_slave]
                if snapshot_sgf_vs_slave
                else await self.compute_control_sgf_vs_slave(
                    params=search_params, sgf=data_sgf, slave=data_slave
                )
            )

            # 3. Upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[list[dict], str]] = [
                (data_siif_vs_slave, "siif_vs_slave_db"),
                (data_sgf_vs_slave, "sgf_vs_slave_db"),
                (data_siif, "siif_db"),
                (data_slave, "slave_db"),
                (data_sgf, "sgf_db"),
            ]
            for records, sheet_name in sheets:
                try:
                    # DataFrame + sanitizado + upload corren en el threadpool
                    await run_in_threadpool(
                        self._build_df_and_upload, records, sheet_name
                    )
                    logger.info(
                        f"Control Honorarios: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Honorarios: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info("Control Honorarios: exportación a Google Sheets finalizada")

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
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_HONORARIOS,
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
        return df.drop(columns=["id"], errors="ignore")


ControlHonorariosServiceDependency = Annotated[ControlHonorariosService, Depends()]
