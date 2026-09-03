__all__ = [
    "ControlHonorariosService",
    "ControlHonorariosServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...siif.schemas import GtoRpa03gFullFilter
from ...siif.services import (
    GtoRpa03gServiceDependency,
)
from ...slave.schemas import HonorariosFullFilter
from ...slave.services import HonorariosServiceDependency
from ...sscc.services import BancoINVICOServiceDependency, CtasCtesServiceDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ControlHonorariosFullFilter,
    ControlHonorariosLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlHonorariosService:
    gastos_service: GtoRpa03gServiceDependency
    slave_service: HonorariosServiceDependency
    sgf_service: ResumenRendProvServiceDependency
    banco_service: BancoINVICOServiceDependency
    cta_cte_service: CtasCtesServiceDependency

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
        df = pd.DataFrame(data)

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Filtramos el DataFrame
        df = df.loc[df["cuit"] == "30632351514"]
        df = df.loc[df["cta_cte"].isin(["130832-05", "130832-07"])]
        keep = ["HONOR", "RECON", "LOC"]
        df = df.loc[df.glosa.str.contains("|".join(keep))]

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

        # 4. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 5. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

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
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Agregamos el campo cta_cte del SIIF
        if not siif:
            siif = await self.get_siif_honorarios(params=params)
        siif = pd.DataFrame(siif)
        siif = siif.loc[:, ["nro_comprobante", "cta_cte"]]
        siif = siif.drop_duplicates()
        df = df.merge(siif, on="nro_comprobante", how="left")
        df = df.fillna(0)

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

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
        df = pd.DataFrame(data)
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Depuramos embargos en la cta_cte 130832-05
        banco_params = ResumenRendProvFullFilter(
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
            df = df.fillna(0)

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

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

        if not siif:
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

        if not slave:
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
        df = df.fillna(0)
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

        return df.to_dict(orient="records")

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

        if not sgf:
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

        if not slave:
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
        df = df.fillna(0)
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

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlHonorariosLiteFilter) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ControlHonorariosFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_siif = await self.get_siif_honorarios(params=params)
        data_slave = await self.get_slave_honorarios(params=params, siif=data_siif)
        data_sgf = await self.get_sgf_honorarios(params=params)
        data_siif_vs_slave = await self.compute_control_siif_vs_slave(
            params=params, siif=data_siif, slave=data_slave
        )
        data_sgf_vs_slave = await self.compute_control_sgf_vs_slave(
            params=params, sgf=data_sgf, slave=data_slave
        )

        # 3. Transformamos los datos a DataFrames de Pandas
        df_siif = pd.DataFrame(data_siif)
        df_slave = pd.DataFrame(data_slave)
        df_sgf = pd.DataFrame(data_sgf)
        df_siif_vs_slave = pd.DataFrame(data_siif_vs_slave)
        df_sgf_vs_slave = pd.DataFrame(data_sgf_vs_slave)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_siif_vs_slave, "siif_vs_slave_db"),
                (df_sgf_vs_slave, "sgf_vs_slave_db"),
                (df_siif, "siif_db"),
                (df_slave, "slave_db"),
                (df_sgf, "sgf_db"),
            ],
            filename="Control Honorarios Factureros.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1fQhp1CdESnvqzrp3QMV5bFSHmGdi7SNoaBRWtmw-JgA",
        )


ControlHonorariosServiceDependency = Annotated[ControlHonorariosService, Depends()]
