__all__ = [
    "ReportePlanillometroService",
    "ReportePlanillometroServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...siif.repositories import PlanillometroHistRepositoryDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ReportePlanillometroFilter,
    ReportePlanillometroLiteFilter,
    ReportePlanillometroReport,
)


@dataclass
# -------------------------------------------------
class ReportePlanillometroService:
    icaro_service: CargaServiceDependency
    planillometro_hist_repo: PlanillometroHistRepositoryDependency

    # -------------------------------------------------
    async def generate(
        self,
        params: ReportePlanillometroFilter,
    ) -> List[ReportePlanillometroReport]:
        icaro_params = CargaFullFilter(
            query_filter="partida~42[1-2]{1}, tipo!=PA6, "
            + f"ejercicio<={int(params.ejercicio)}",
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
            if not df_last.empty:
                df_last["ejercicio"] = df_last["ejercicio"].astype(int)
                df = pd.concat([df, df_last], axis=0, ignore_index=True)

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

                estructuras_unicas = set(df["estructura"].unique())
                df_dif = df_acum_2008.loc[
                    df_acum_2008["estructura"].isin(estructuras_unicas)
                ].copy()
                df_dif = df_dif.drop(
                    columns=[
                        "desc_programa",
                        "desc_subprograma",
                        "desc_proyecto",
                        "desc_actividad",
                    ],
                    errors="ignore",
                )

                columns_to_merge = [
                    "estructura",
                    "desc_programa",
                    "desc_proyecto",
                    "desc_actividad",
                ]
                if params.desagregar_desc_subprog:
                    columns_to_merge.insert(2, "desc_subprograma")

                df_dif = pd.merge(
                    df_dif,
                    df.loc[:, columns_to_merge].drop_duplicates(),
                    on=["estructura"],
                    how="left",
                )
                df_acum_2008 = df_acum_2008.loc[
                    ~df_acum_2008["estructura"].isin(df_dif["estructura"].unique())
                ]
                df_acum_2008 = pd.concat([df_acum_2008, df_dif])
                df = pd.concat([df, df_acum_2008], ignore_index=True)
                df = df.drop(columns=["estructura"], errors="ignore")

        # # Ejercicio alta
        # df_alta = df.groupby(group_cols).ejercicio.min().reset_index()
        # df_alta.rename(columns={"ejercicio": "alta"}, inplace=True)

        # # Ejercicios a procesar
        # ejercicios = sorted(df["ejercicio"].unique(), reverse=True)
        # if params.ultimos_ejercicios is not None:
        #     ejercicios = ejercicios[: int(params.ultimos_ejercicios)]

        # set_ejercicios = set(ejercicios)

        # # Ejercicio actual
        # df_ejec_actual = df.copy()
        # df_ejec_actual = df_ejec_actual.loc[df_ejec_actual.ejercicio.isin(ejercicios)]
        # df_ejec_actual = (
        #     df_ejec_actual.groupby(group_cols + ["ejercicio"])
        #     .importe.sum()
        #     .reset_index()
        # )
        # df_ejec_actual.rename(columns={"importe": "ejecucion"}, inplace=True)

        # # Ejecucion Acumulada
        # df_acum = pd.DataFrame()
        # for ejercicio in ejercicios:
        #     df_ejercicio = df.copy()
        #     df_ejercicio = df_ejercicio.loc[
        #         df_ejercicio.ejercicio.astype(int) <= int(ejercicio)
        #     ]
        #     df_ejercicio["ejercicio"] = ejercicio
        #     df_ejercicio = (
        #         df_ejercicio.groupby(group_cols + ["ejercicio"])
        #         .importe.sum()
        #         .reset_index()
        #     )

        #     df_ejercicio.rename(columns={"importe": "acum"}, inplace=True)
        #     df_acum = pd.concat([df_acum, df_ejercicio])

        # # Obras en curso
        # df_curso = pd.DataFrame()
        # for ejercicio in ejercicios:
        #     df_ejercicio = df.copy()
        #     df_ejercicio = df_ejercicio.loc[
        #         df_ejercicio.ejercicio.astype(int) <= int(ejercicio)
        #     ]
        #     df_ejercicio["ejercicio"] = ejercicio
        #     obras_curso = df_ejercicio.groupby(["desc_obra"]).avance.max().to_frame()
        #     obras_curso = (
        #         obras_curso.loc[obras_curso.avance < 1].reset_index().desc_obra
        #     )
        #     df_ejercicio = (
        #         df_ejercicio.loc[df_ejercicio.desc_obra.isin(obras_curso)]
        #         .groupby(group_cols + ["ejercicio"])
        #         .importe.sum()
        #         .reset_index()
        #     )
        #     df_ejercicio.rename(columns={"importe": "en_curso"}, inplace=True)
        #     df_curso = pd.concat([df_curso, df_ejercicio])

        # # Obras terminadas anterior
        # df_term_ant = pd.DataFrame()
        # for ejercicio in ejercicios:
        #     df_ejercicio = df.copy()
        #     df_ejercicio = df_ejercicio.loc[
        #         df_ejercicio.ejercicio.astype(int) < int(ejercicio)
        #     ]
        #     df_ejercicio["ejercicio"] = ejercicio
        #     obras_term_ant = df_ejercicio.groupby(["desc_obra"]).avance.max().to_frame()
        #     obras_term_ant = (
        #         obras_term_ant.loc[obras_term_ant.avance == 1].reset_index().desc_obra
        #     )
        #     df_ejercicio = (
        #         df_ejercicio.loc[df_ejercicio.desc_obra.isin(obras_term_ant)]
        #         .groupby(group_cols + ["ejercicio"])
        #         .importe.sum()
        #         .reset_index()
        #     )
        #     df_ejercicio.rename(columns={"importe": "terminadas_ant"}, inplace=True)
        #     df_term_ant = pd.concat([df_term_ant, df_ejercicio])

        # df = pd.merge(df_alta, df_acum, on=group_cols, how="left")
        # df = pd.merge(df, df_ejec_actual, on=group_cols + ["ejercicio"], how="left")
        # cols = df.columns.tolist()
        # penultima_col = cols.pop(-2)  # Elimina la penúltima columna y la guarda
        # cols.append(penultima_col)  # Agrega la penúltima columna al final
        # df = df[cols]  # Reordena las columnas
        # df = pd.merge(df, df_curso, on=group_cols + ["ejercicio"], how="left")
        # df = pd.merge(df, df_term_ant, on=group_cols + ["ejercicio"], how="left")
        # df = df.fillna(0)
        # df["terminadas_actual"] = df.acum - df.en_curso - df.terminadas_ant
        # df["actividad"] = df["actividad"] + "-" + df["partida"]
        # df = df.rename(columns={"actividad": "estructura"})
        # if not params.desagregar_partida:
        #     df = df.drop(columns=["partida"])

        # if params.limit is not None and params.limit > 0:
        #     df = df.head(params.limit)

        # df = sanitize_dataframe_for_json_with_datetime(df)
        # json_data = df.to_dict(orient="records")

        # Ejercicios a procesar
        ejercicios_unicos = sorted(df["ejercicio"].unique(), reverse=True)
        if params.ultimos_ejercicios is not None:
            ejercicios_unicos = ejercicios_unicos[: int(params.ultimos_ejercicios)]

        # --- 1. MATRIZ DE ESTRUCTURAS Y ALTA HISTÓRICA COMPLETA ---
        # Calculamos el alta tomando el dataset completo para no perder la primera aparición histórica
        df_alta = df.groupby(group_cols).ejercicio.min().reset_index()
        df_alta.rename(columns={"ejercicio": "alta"}, inplace=True)

        # print("df_alta", len(df_alta), df_alta.columns, df_alta.head())

        # Estructuras únicas
        idx_estructuras = df_alta[group_cols].drop_duplicates()

        # Generamos la grilla completa: (Todas las estructuras x Todos los ejercicios solicitados)
        grid_frames = []
        for ej in ejercicios_unicos:
            temp = idx_estructuras.copy()
            temp["ejercicio"] = ej
            grid_frames.append(temp)

        # print("grid_frames", len(grid_frames), grid_frames[0].head())

        df_base_grid = pd.concat(grid_frames, ignore_index=True)
        df_base_grid = pd.merge(df_base_grid, df_alta, on=group_cols, how="left")

        # print("df_base_grid", len(df_base_grid), df_base_grid.head())

        # --- 2. CÁLCULO DE EJECUCIÓN (Sin perder filas sin movimiento) ---
        df_ejec = (
            df.groupby(group_cols + ["ejercicio"])["importe"]
            .sum()
            .reset_index()
            .rename(columns={"importe": "ejecucion"})
        )

        # --- 3. CÁLCULO DE ACUMULADOS HISTÓRICOS ---
        # Para evitar que cumsum omita años sin movimientos, acumulamos por ejercicio directamente sobre df
        # Calculamos el acumulado de importe para cada combinación (group_cols + ejercicio_corte)
        df_acum_list = []
        for ej in ejercicios_unicos:
            df_sub = df.loc[df["ejercicio"] <= ej]
            if not df_sub.empty:
                df_temp = (
                    df_sub.groupby(group_cols)["importe"]
                    .sum()
                    .reset_index()
                    .rename(columns={"importe": "acum"})
                )
                df_temp["ejercicio"] = ej
                df_acum_list.append(df_temp)

        df_acum = (
            pd.concat(df_acum_list, ignore_index=True)
            if df_acum_list
            else pd.DataFrame(columns=group_cols + ["ejercicio", "acum"])
        )

        # # --- 4. OBRAS EN CURSO Y TERMINADAS (Fiel a la lógica de dominio + Cero CPU) ---
        # df_curso_list = []
        # df_term_ant_list = []

        # if "desc_obra" in df.columns and not df.empty:
        #     # 1. Agrupamos por (group_cols + desc_obra + ejercicio) para no cruzar estructuras
        #     keys_obra = list(set(group_cols + ["desc_obra"]))

        #     # Matriz de avance histórico por obra dentro de su estructura
        #     df_obras_hist = (
        #         df.groupby(keys_obra + ["ejercicio"])["avance"].max().reset_index()
        #     )

        #     for ej in ejercicios_unicos:
        #         ej_int = int(ej)

        #         # --- A. OBRAS EN CURSO (hasta el ejercicio ej) ---
        #         # Subconjunto de avances HASTA el ejercicio evaluado
        #         sub_avances_le = df_obras_hist.loc[df_obras_hist["ejercicio"] <= ej_int]
        #         if not sub_avances_le.empty:
        #             # Máximo avance que alcanzó la obra HASTA este ejercicio
        #             max_le = (
        #                 sub_avances_le.groupby(keys_obra)["avance"].max().reset_index()
        #             )
        #             # Filtramos solo las que están en curso (< 1)
        #             obras_curso = max_le.loc[max_le["avance"] < 1, keys_obra]

        #             if not obras_curso.empty:
        #                 # Unimos con df (filtro exacto <= ej_int sobre esas obras)
        #                 df_c = (
        #                     pd.merge(
        #                         df.loc[df["ejercicio"] <= ej_int],
        #                         obras_curso,
        #                         on=keys_obra,
        #                         how="inner",
        #                     )
        #                     .groupby(group_cols)["importe"]
        #                     .sum()
        #                     .reset_index()
        #                     .rename(columns={"importe": "en_curso"})
        #                 )
        #                 df_c["ejercicio"] = ej
        #                 df_curso_list.append(df_c)

        #         # --- B. OBRAS TERMINADAS ANTERIOR (estrictamente ANTES de ej) ---
        #         # Subconjunto de avances ANTES del ejercicio evaluado (< ej_int)
        #         sub_avances_lt = df_obras_hist.loc[df_obras_hist["ejercicio"] < ej_int]
        #         if not sub_avances_lt.empty:
        #             # Máximo avance que alcanzó la obra ANTES de este ejercicio
        #             max_lt = (
        #                 sub_avances_lt.groupby(keys_obra)["avance"].max().reset_index()
        #             )
        #             # Filtramos solo las que YA estaban terminadas (== 1) antes de este ejercicio
        #             obras_term_ant = max_lt.loc[max_lt["avance"] == 1, keys_obra]

        #             if not obras_term_ant.empty:
        #                 # Unimos con df (filtro exacto < ej_int sobre esas obras)
        #                 df_t = (
        #                     pd.merge(
        #                         df.loc[df["ejercicio"] < ej_int],
        #                         obras_term_ant,
        #                         on=keys_obra,
        #                         how="inner",
        #                     )
        #                     .groupby(group_cols)["importe"]
        #                     .sum()
        #                     .reset_index()
        #                     .rename(columns={"importe": "terminadas_ant"})
        #                 )
        #                 df_t["ejercicio"] = ej
        #                 df_term_ant_list.append(df_t)

        # # Consolidación final
        # df_curso = (
        #     pd.concat(df_curso_list, ignore_index=True)
        #     if df_curso_list
        #     else pd.DataFrame(columns=group_cols + ["ejercicio", "en_curso"])
        # )
        # df_term_ant = (
        #     pd.concat(df_term_ant_list, ignore_index=True)
        #     if df_term_ant_list
        #     else pd.DataFrame(columns=group_cols + ["ejercicio", "terminadas_ant"])
        # )

        # --- 5. CONSOLIDACIÓN SOBRE LA MATRIZ BASE ---
        df_final = pd.merge(
            df_base_grid, df_ejec, on=group_cols + ["ejercicio"], how="left"
        )
        df_final = pd.merge(
            df_final, df_acum, on=group_cols + ["ejercicio"], how="left"
        )
        # df_final = pd.merge(
        #     df_final, df_curso, on=group_cols + ["ejercicio"], how="left"
        # )
        # df_final = pd.merge(
        #     df_final, df_term_ant, on=group_cols + ["ejercicio"], how="left"
        # )

        # # Rellenar ceros
        # df_final.fillna(
        #     {"en_curso": 0, "terminadas_ant": 0, "ejecucion": 0, "acum": 0},
        #     inplace=True,
        # )

        # df_final["terminadas_actual"] = (
        #     df_final["acum"] - df_final["en_curso"] - df_final["terminadas_ant"]
        # )
        df_final["actividad"] = df_final["actividad"] + "-" + df_final["partida"]
        df_final.rename(columns={"actividad": "estructura"}, inplace=True)

        if not params.desagregar_partida:
            df_final.drop(columns=["partida"], inplace=True, errors="ignore")

        # --- 6. REORDENAMIENTO DE COLUMNAS (alta antes que ejercicio) ---
        cols = df_final.columns.tolist()
        if "alta" in cols and "ejercicio" in cols:
            cols.remove("alta")
            ej_idx = cols.index("ejercicio")
            cols.insert(ej_idx, "alta")  # Insertar 'alta' justo antes de 'ejercicio'
            df_final = df_final[cols]

        df_final.sort_values(
            ["estructura", "ejercicio"], ascending=[True, False], inplace=True
        )

        # --- 7. Elimino los registros cuyo campo alta es mayor que ejercicio
        df_final = df_final.loc[df_final["alta"] <= df_final["ejercicio"]]
        df_final["alta"] = df_final["alta"].astype(str)

        if params.limit is not None and params.limit > 0:
            df_final = df_final.head(params.limit)

        df_final = sanitize_dataframe_for_json_with_datetime(df_final)

        return df_final.to_dict(orient="records")

    # -------------------------------------------------
    async def export_eecc(
        self, params: ReportePlanillometroLiteFilter
    ) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        icaro_params = ReportePlanillometroFilter(
            ejercicio=str(params.ejercicio),
            ultimos_ejercicios=5,
            include_pa6=False,
            desagregar_desc_subprog=False,
            limit=None,  # Para traer todo
        )
        # 2. Traemos los datos sin paginar
        data_planillometro = await self.generate(params=icaro_params)

        # 3. Usar el método de la clase base
        df_planillometro = pd.DataFrame(data_planillometro)
        df_planillometro = df_planillometro.rename(
            columns={
                "desc_programa": "desc_prog",
                "desc_proyecto": "desc_proy",
                "desc_actividad": "desc_act",
            }
        )

        # sgv = await get_sgv_saldos_barrios_evolucion()
        # sgv["ejercicio"] = sgv["ejercicio"].astype(str)
        # sgv["cod_barrio"] = sgv["cod_barrio"].astype(int)
        # sgv = sgv.sort_values(by=["ejercicio", "cod_barrio"], ascending=[True, True])

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_planillometro, "bd_planillometro"),
                # (sgv, "bd_recuperos"),
            ],
            filename="Reporte Planillometro.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1Hmb7xmzhZBoicnL5_tN7mr1kOj-r3gw8lCkPErR8Xd4",
        )


ReportePlanillometroServiceDependency = Annotated[
    ReportePlanillometroService, Depends()
]
