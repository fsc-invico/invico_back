__all__ = ["ControlIcaroService", "ControlIcaroServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...siif.schemas import (
    GtoRpa03gFullFilter,
    Rf602FullFilter,
)
from ...siif.services import (
    GtoRpa03gServiceDependency,
    Rf602ServiceDependency,
)

# from pydantic import ValidationError
from ...utils import (
    BaseService,
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..repositories import (
    ControlIcaroAnualRepositoryDependency,
    ControlIcaroComprobantesRepositoryDependency,
    ControlIcaroPA6RepositoryDependency,
)
from ..schemas import (
    ControlIcaroFullFilter,
    ControlIcaroLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlIcaroService:
    ctrl_anual: ControlIcaroAnualRepositoryDependency
    ctrl_comprobantes: ControlIcaroComprobantesRepositoryDependency
    ctrl_pa6: ControlIcaroPA6RepositoryDependency
    gastos_service: GtoRpa03gServiceDependency
    icaro_service: CargaServiceDependency
    rf602_service: Rf602ServiceDependency

    # -------------------------------------------------
    async def get_siif_comprobantes(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        # gastos_params.set_extra_filter({"partida": {"$in": ["421", "422", "354"]}})
        gastos_params.set_extra_filter(
            {
                "$or": [
                    {"partida": {"$in": ["421", "422"]}},
                    {
                        "$and": [
                            {"partida": "354"},
                            {
                                "cuit": {
                                    "$nin": [
                                        "30500049460",
                                        "30632351514",
                                        "20231243527",
                                    ]
                                }
                            },
                        ]
                    },
                ]
            }
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

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def get_icaro_comprobantes(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        icaro_params = CargaFullFilter(
            query_filter="tipo!=PA6",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.icaro_service.get_all(params=icaro_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe
        df["estructura"] = df.actividad + "-" + df.partida

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def get_siif_obras(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        rf602_params = Rf602FullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        rf602_params.set_extra_filter(
            {
                "$or": [
                    {"partida": {"$in": ["421", "422"]}},
                    {"estructura": "01-00-00-03-354"},
                ]
            }
        )

        data = await self.rf602_service.get_all(params=rf602_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_anual(
        self,
        params: ControlIcaroFullFilter,
        icaro: list[dict] = None,
        siif: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "estructura", "fuente"]

        if not icaro:
            icaro = await self.get_icaro_comprobantes(params=params)
        icaro = pd.DataFrame(icaro)
        icaro = icaro.groupby(groupby_cols)["importe"].sum()
        icaro = icaro.reset_index()
        icaro = icaro.rename(columns={"importe": "ejecucion_icaro"})
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not siif:
            siif = await self.get_siif_obras(params=params)
        siif = pd.DataFrame(siif)
        siif = siif.loc[:, groupby_cols + ["ordenado"]]
        siif = siif.rename(columns={"ordenado": "ejecucion_siif"})
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(siif, icaro, how="outer", on=groupby_cols)
        df = df.fillna(0)
        df["diferencia"] = df["ejecucion_siif"] - df["ejecucion_icaro"]

        # df = df.merge(
        #     get_siif_desc_pres(ejercicio_to=ejercicio),
        #     how="left",
        #     on="estructura",
        #     copy=False,
        # )
        df = df.loc[(df["diferencia"] < -0.2) | (df["diferencia"] > 0.2)]
        df = df.reset_index(drop=True)
        df["fuente"] = pd.to_numeric(df["fuente"], errors="coerce")
        df["ejercicio"] = pd.to_numeric(df["ejercicio"], errors="coerce")

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlIcaroLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ControlIcaroFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_ctrl_anual = await self.ctrl_anual.find_with_filter_params(
            params=search_params
        )
        df_ctrl_anual = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_anual]
        )
        data_ctrl_comprobantes = await self.ctrl_comprobantes.find_with_filter_params(
            params=search_params
        )
        df_ctrl_comprobantes = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_comprobantes]
        )
        data_ctrl_pa6 = await self.ctrl_pa6.find_with_filter_params(
            params=search_params
        )
        df_ctrl_pa6 = pd.DataFrame([d.model_dump(by_alias=True) for d in data_ctrl_pa6])

        # 3. Usar el método de la clase base
        return BaseService.export_to_excel(
            self,
            data_pairs=[
                (
                    df_ctrl_anual,
                    "control_ejecucion_anual_db",
                ),
                (
                    df_ctrl_comprobantes,
                    "control_comprobantes_db",
                ),
                (
                    df_ctrl_pa6,
                    "control_pa6_db",
                ),
            ],
            filename="Control Icaro vs SIIF.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1KKeeoop_v_Nf21s7eFp4sS6SmpxRZQ9DPa1A5wVqnZ0",
        )


ControlIcaroServiceDependency = Annotated[ControlIcaroService, Depends()]
