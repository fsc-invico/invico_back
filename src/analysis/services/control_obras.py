__all__ = ["ControlObrasService", "ControlObrasServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ControlObrasFullFilter,
    ControlObrasLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlObrasService:
    resumen_rend_service: ResumenRendProvServiceDependency
    icaro_service: CargaServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def export(self, params: ControlObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        params = ControlObrasFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_sgf = await self.get_sgf_resumend_rend(params=params)
        data_icaro = await self.get_icaro_carga_neto_rdeu(params=params)
        data_ctrl_obras = await self.compute_control_obras(
            params=params, sgf=data_sgf, icaro=data_icaro
        )

        # 3. Usar el método de la clase base
        df_ctrl_obras = pd.DataFrame(data_ctrl_obras)
        df_sgf = pd.DataFrame(data_sgf)
        df_icaro = pd.DataFrame(data_icaro)
        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_ctrl_obras, "control_mes_cta_cte_cuit_db_new"),
                (df_sgf, "resumen_rend_cuit_new"),
                (df_icaro, "icaro_carga_neto_rdeu_new"),
            ],
            filename="Control Obras.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="16v2ovmQnS1v73-WxTOK6b9Tx9DRugGc70ufpjVi-rPA",
        )

    # -------------------------------------------------
    async def get_icaro_carga_neto_rdeu(
        self,
        params: ControlObrasFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        icaro_params = CargaFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.icaro_service.carga_neto_rdeu(params=icaro_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "icaro_cta_cte")

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_sgf_resumend_rend(
        self,
        params: ControlObrasFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        sgf_params = ResumenRendProvFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.resumen_rend_service.unique_obras(params=sgf_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "sgf_cta_cte")

        # 3. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_obras(
        self,
        params: ControlObrasFullFilter,
        icaro: list[dict] = None,
        sgf: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        group_by = ["ejercicio", "mes", "cta_cte", "cuit"]

        if not icaro:
            icaro = await self.get_icaro_carga_neto_rdeu(params=params)
        icaro = pd.DataFrame(icaro)
        if not icaro.empty:
            icaro = icaro.loc[:, group_by + ["importe"]]
            icaro = icaro.groupby(group_by)["importe"].sum().reset_index()
            icaro = icaro.rename(columns={"importe": "ejecutado_icaro"})
        else:
            icaro = pd.DataFrame(columns=group_by + ["ejecutado_icaro"])
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not sgf:
            sgf = await self.get_sgf_resumend_rend(params=params)
        sgf = pd.DataFrame(sgf)
        if not sgf.empty:
            sgf = sgf.loc[:, group_by + ["importe_bruto"]]
            sgf = sgf.groupby(group_by)["importe_bruto"].sum().reset_index()
            sgf = sgf.rename(columns={"importe_bruto": "bruto_sgf"})
        else:
            sgf = pd.DataFrame(columns=group_by + ["bruto_sgf"])
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(icaro, sgf, how="outer", on=group_by)
        df[["ejecutado_icaro", "bruto_sgf"]] = df[
            ["ejecutado_icaro", "bruto_sgf"]
        ].fillna(0)
        df["diferencia"] = df["ejecutado_icaro"] - df["bruto_sgf"]

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # # -------------------------------------------------
    # async def compute_control_obras_old(
    #     self, ejercicios: List[int]
    # ) -> List[RouteReturnSchema]:
    #     results: List[RouteReturnSchema] = []
    #     group_by = ["ejercicio", "mes", "cta_cte", "cuit"]

    #     if isinstance(ejercicios, int):
    #         ejercicios = [ejercicios]

    #     for ejercicio in ejercicios:
    #         # 2. Reutilizamos las funciones del Back sin salir a internet (Velocidad local de servidor)
    #         resumen_rend_params = ResumenRendProvFullFilter(
    #             query_filter="",
    #             ejercicio=str(ejercicio),
    #             limit=None,  # Para traer todo
    #             origen=None,
    #         )
    #         icaro_params = CargaFullFilter(
    #             query_filter="",
    #             ejercicio=str(ejercicio),
    #             limit=None,
    #         )

    #         # Llamadas asincrónicas nativas cruzando lógica
    #         data_icaro = await self.icaro_service.carga_neto_rdeu(params=icaro_params)
    #         data_sgf = await self.resumen_rend_service.unique_obras(
    #             params=resumen_rend_params
    #         )  # O unique_obras según tu lógica

    #         # 3. Procesamiento en memoria ultra veloz con Pandas en el Back
    #         icaro = pd.DataFrame(data_icaro)
    #         if not icaro.empty:
    #             icaro = icaro.loc[:, group_by + ["importe"]]
    #             icaro = icaro.groupby(group_by)["importe"].sum().reset_index()
    #             icaro = icaro.rename(columns={"importe": "ejecutado_icaro"})
    #         else:
    #             icaro = pd.DataFrame(columns=group_by + ["ejecutado_icaro"])

    #         sgf = pd.DataFrame(data_sgf)
    #         if not sgf.empty:
    #             sgf = sgf.loc[:, group_by + ["importe_bruto"]]
    #             sgf = sgf.groupby(group_by)["importe_bruto"].sum().reset_index()
    #             sgf = sgf.rename(columns={"importe_bruto": "bruto_sgf"})
    #         else:
    #             sgf = pd.DataFrame(columns=group_by + ["bruto_sgf"])

    #         # 4. El Cruce de Datos
    #         df = pd.merge(icaro, sgf, how="outer", on=group_by)
    #         df[["ejecutado_icaro", "bruto_sgf"]] = df[
    #             ["ejecutado_icaro", "bruto_sgf"]
    #         ].fillna(0)
    #         df["diferencia"] = df["ejecutado_icaro"] - df["bruto_sgf"]

    #         # Sanitizamos antes de guardar/retornar
    #         df = sanitize_dataframe_for_json_with_datetime(df)
    #         json_data = df.to_dict(orient="records")

    #         # 5. Guardamos directamente en la base de datos desde acá
    #         if json_data:
    #             # Mapeamos cada fila del diccionario al esquema que espera el método
    #             lista_modelos = [ControlObrasReport(**fila) for fila in json_data]

    #             # Llamamos al método del propio servicio con toda su lógica e idempotencia
    #             response = await self.add_many(data=lista_modelos)

    #             results.append(response)
    #         else:
    #             results.append(f"Ejercicio {ejercicio}: Sin datos para procesar")

    #     return results


ControlObrasServiceDependency = Annotated[ControlObrasService, Depends()]
