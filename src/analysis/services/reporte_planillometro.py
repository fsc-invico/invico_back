__all__ = ["ReportePlanillometroService", "ReportePlanillometroServiceDependency"]

from dataclasses import dataclass
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...siif.repositories import PlanillometroHistRepositoryDependency
from ...utils import sanitize_dataframe_for_json_with_datetime
from ..repositories import ControlObrasRepositoryDependency
from ..schemas import (
    ControlObrasFullFilter,
    ControlObrasLiteFilter,
    ReportePlanillometroFilter,
    ReportePlanillometroReport,
)


@dataclass
# -------------------------------------------------
class ReportePlanillometroService:
    ctrl_obras: ControlObrasRepositoryDependency
    resumen_rend_service: ResumenRendProvServiceDependency
    icaro_service: CargaServiceDependency
    planillometro_hist_repo: PlanillometroHistRepositoryDependency

    # -------------------------------------------------
    async def export(self, params: ControlObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        ctrl_obras_params = ControlObrasFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        resumen_rend_params = ResumenRendProvFullFilter(
            query_filter="",
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
            origen=None,
        )
        icaro_params = CargaFullFilter(
            query_filter="",
            ejercicio=params.ejercicio,
            limit=None,
        )

        # 2. Traemos los datos sin paginar
        data_ctrl_obras = await self.ctrl_obras.find_with_filter_params(
            params=ctrl_obras_params
        )
        data_sgf = await self.resumen_rend_service.unique_obras(
            params=resumen_rend_params
        )
        data_icaro = await self.icaro_service.neto_rdeu(params=icaro_params)

        # 3. Usar el método de la clase base
        df_ctrl_obras = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_obras]
        )
        df_sgf = pd.DataFrame(data_sgf)
        df_icaro = pd.DataFrame(data_icaro)
        return self.export_to_excel(
            data_pairs=[
                (df_ctrl_obras, "control_mes_cta_cte_cuit_db"),
                (df_sgf, "resumen_rend_cuit"),
                (df_icaro, "icaro_carga_neto_rdeu"),
            ],
            filename="Control Obras.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="16v2ovmQnS1v73-WxTOK6b9Tx9DRugGc70ufpjVi-rPA",
        )

    # -------------------------------------------------
    async def generate_planillometro_icaro(
        self,
        params: ReportePlanillometroFilter,
    ) -> List[ReportePlanillometroReport]:
        icaro_params = CargaFullFilter(
            query_filter="partida~42[1-2]{1}, tipo!=PA6",
            ejercicio=params.ejercicio,
            limit=None,
        )
        df = pd.DataFrame(await self.icaro_service.full_desc_siif(params=icaro_params))
        df.sort_values(["actividad", "partida", "fuente"], inplace=True)

        # Grupos de columnas
        group_cols = ["desc_programa"]
        if params.desagregar_desc_subprog:
            group_cols = group_cols + ["desc_subprograma"]
        group_cols = group_cols + [
            "desc_proyecto",
            "desc_actividad",
            "actividad",
            "partida",
        ]
        if params.desagregar_obras:
            group_cols = group_cols + ["desc_obra"]
        if params.desagregar_fuente:
            group_cols = group_cols + ["fuente"]

        # Eliminamos aquellos ejercicios anteriores a 2009
        df = df.loc[df.ejercicio.astype(int) >= 2009]

        # Incluimos PA6 (ultimo ejercicio)
        if params.include_pa6:
            df = df.loc[df.ejercicio.astype(int) < int(params.ejercicio)]
            icaro_params = CargaFullFilter(
                query_filter="partida~42[1-2]{1}, tipo!=REG",
                ejercicio=params.ejercicio,
                limit=None,
            )
            df_last = pd.DataFrame(
                await self.icaro_service.full_desc_siif(params=icaro_params)
            )
            df = pd.concat([df, df_last], axis=0)

        # Filtramos hasta una fecha máxima
        if params.date_up_to:
            date_up_to = np.datetime64(params.date_up_to)
            df = df.loc[df["fecha"] <= date_up_to]

        # Agregamos ejecución acumulada de Patricia
        if params.agregar_acum_2008:
            df_acum_2008 = pd.DataFrame(await self.planillometro_hist_repo.get_all())
            if not df_acum_2008.empty:
                df_acum_2008["ejercicio"] = 2008
                df_acum_2008["avance"] = 1
                df_acum_2008["desc_obra"] = df_acum_2008["desc_actividad"]
                df_acum_2008 = df_acum_2008.rename(columns={"acum_2008": "importe"})
                df["estructura"] = df["actividad"] + "-" + df["partida"]
                df_dif = df_acum_2008.loc[
                    df_acum_2008["estructura"].isin(df["estructura"].unique().tolist())
                ]
                df_dif = df_dif.drop(
                    columns=[
                        "desc_programa",
                        "desc_subprograma",
                        "desc_proyecto",
                        "desc_actividad",
                    ]
                )
                if params.desagregar_desc_subprog:
                    columns_to_merge = [
                        "estructura",
                        "desc_programa",
                        "desc_subprograma",
                        "desc_proyecto",
                        "desc_actividad",
                    ]
                else:
                    columns_to_merge = [
                        "estructura",
                        "desc_programa",
                        "desc_proyecto",
                        "desc_actividad",
                    ]
                df_dif = pd.merge(
                    df_dif,
                    df.loc[:, columns_to_merge].drop_duplicates(),
                    on=["estructura"],
                    how="left",
                )
                df_acum_2008 = df_acum_2008.loc[
                    ~df_acum_2008["estructura"].isin(
                        df_dif["estructura"].unique().tolist()
                    )
                ]
                df_acum_2008 = pd.concat([df_acum_2008, df_dif])
                df = pd.concat([df, df_acum_2008])
                df = df.drop(columns=["estructura"])

        # Ejercicio alta
        df_alta = df.groupby(group_cols).ejercicio.min().reset_index()
        df_alta.rename(columns={"ejercicio": "alta"}, inplace=True)

        df_ejercicios = df.copy()
        if params.ultimos_ejercicios is None:
            ejercicios = df_ejercicios.sort_values(
                "ejercicio", ascending=False
            ).ejercicio.unique()
        else:
            ejercicios = int(params.ultimos_ejercicios)
            ejercicios = df_ejercicios.sort_values(
                "ejercicio", ascending=False
            ).ejercicio.unique()[0:ejercicios]
            # df_anos = df_anos.loc[df_anos.ejercicio.isin(ejercicios)]

        # Ejercicio actual
        df_ejec_actual = df.copy()
        df_ejec_actual = df_ejec_actual.loc[df_ejec_actual.ejercicio.isin(ejercicios)]
        df_ejec_actual = (
            df_ejec_actual.groupby(group_cols + ["ejercicio"])
            .importe.sum()
            .reset_index()
        )
        df_ejec_actual.rename(columns={"importe": "ejecucion"}, inplace=True)

        # Ejecucion Acumulada
        df_acum = pd.DataFrame()
        for ejercicio in ejercicios:
            df_ejercicio = df.copy()
            df_ejercicio = df_ejercicio.loc[
                df_ejercicio.ejercicio.astype(int) <= int(ejercicio)
            ]
            df_ejercicio["ejercicio"] = ejercicio
            df_ejercicio = (
                df_ejercicio.groupby(group_cols + ["ejercicio"])
                .importe.sum()
                .reset_index()
            )

            df_ejercicio.rename(columns={"importe": "acum"}, inplace=True)
            df_acum = pd.concat([df_acum, df_ejercicio])

        # Obras en curso
        df_curso = pd.DataFrame()
        for ejercicio in ejercicios:
            df_ejercicio = df.copy()
            df_ejercicio = df_ejercicio.loc[
                df_ejercicio.ejercicio.astype(int) <= int(ejercicio)
            ]
            df_ejercicio["ejercicio"] = ejercicio
            obras_curso = df_ejercicio.groupby(["desc_obra"]).avance.max().to_frame()
            obras_curso = (
                obras_curso.loc[obras_curso.avance < 1].reset_index().desc_obra
            )
            df_ejercicio = (
                df_ejercicio.loc[df_ejercicio.desc_obra.isin(obras_curso)]
                .groupby(group_cols + ["ejercicio"])
                .importe.sum()
                .reset_index()
            )
            df_ejercicio.rename(columns={"importe": "en_curso"}, inplace=True)
            df_curso = pd.concat([df_curso, df_ejercicio])

        # Obras terminadas anterior
        df_term_ant = pd.DataFrame()
        for ejercicio in ejercicios:
            df_ejercicio = df.copy()
            df_ejercicio = df_ejercicio.loc[
                df_ejercicio.ejercicio.astype(int) < int(ejercicio)
            ]
            df_ejercicio["ejercicio"] = ejercicio
            obras_term_ant = df_ejercicio.groupby(["desc_obra"]).avance.max().to_frame()
            obras_term_ant = (
                obras_term_ant.loc[obras_term_ant.avance == 1].reset_index().desc_obra
            )
            df_ejercicio = (
                df_ejercicio.loc[df_ejercicio.desc_obra.isin(obras_term_ant)]
                .groupby(group_cols + ["ejercicio"])
                .importe.sum()
                .reset_index()
            )
            df_ejercicio.rename(columns={"importe": "terminadas_ant"}, inplace=True)
            df_term_ant = pd.concat([df_term_ant, df_ejercicio])

        df = pd.merge(df_alta, df_acum, on=group_cols, how="left")
        df = pd.merge(df, df_ejec_actual, on=group_cols + ["ejercicio"], how="left")
        cols = df.columns.tolist()
        penultima_col = cols.pop(-2)  # Elimina la penúltima columna y la guarda
        cols.append(penultima_col)  # Agrega la penúltima columna al final
        df = df[cols]  # Reordena las columnas
        df = pd.merge(df, df_curso, on=group_cols + ["ejercicio"], how="left")
        df = pd.merge(df, df_term_ant, on=group_cols + ["ejercicio"], how="left")
        df = df.fillna(0)
        df["terminadas_actual"] = df.acum - df.en_curso - df.terminadas_ant
        df["actividad"] = df["actividad"] + "-" + df["partida"]
        df = df.rename(columns={"actividad": "estructura"})
        if not params.desagregar_partida:
            df = df.drop(columns=["partida"])

        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data


ReportePlanillometroServiceDependency = Annotated[
    ReportePlanillometroService, Depends()
]
