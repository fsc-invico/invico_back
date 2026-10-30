__all__ = [
    "ReportePlanillometroService",
    "ReportePlanillometroServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...config import logger
from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...siif.repositories import PlanillometroHistRepositoryDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ReportePlanillometroRepositoryDependency
from ..schemas import (
    ReportePlanillometroDocument,
    ReportePlanillometroFullFilter,
    ReportePlanillometroGenerateFilter,
    ReportePlanillometroLiteFilter,
    ReportePlanillometroReport,
)


@dataclass
# -------------------------------------------------
class ReportePlanillometroService(
    BaseService[
        ReportePlanillometroReport,
        ReportePlanillometroDocument,
        ReportePlanillometroFullFilter,
        ReportePlanillometroLiteFilter,
    ]
):
    icaro_service: CargaServiceDependency
    planillometro_hist_repo: PlanillometroHistRepositoryDependency
    repository: ReportePlanillometroRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ReportePlanillometroFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def generate(
        self,
        params: ReportePlanillometroGenerateFilter,
    ) -> List[ReportePlanillometroReport]:

        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        icaro_params = CargaFullFilter(
            query_filter="partida~42[1-2]{1}, tipo!=PA6, "
            + f"ejercicio<={int(params.ejercicio)}",
            limit=None,
        )
        # Filtramos hasta una fecha máxima (no funciona, HAY QUE HACERLO EN MONGO usando params)
        # if params.date_up_to:
        #     date_up_to = np.datetime64(params.date_up_to)
        #     df = df.loc[df["fecha"] <= date_up_to]

        # Traemos el DF agrupado
        campos_agrupacion = ["ejercicio", "actividad", "partida", "desc_obra"]
        if params.desagregar_fuente:
            campos_agrupacion.insert(1, "fuente")
            print(campos_agrupacion)
        df = pd.DataFrame(
            await self.icaro_service.acum_with_desc_siif(
                params=icaro_params, groub_by=campos_agrupacion
            )
        )
        df.sort_values(["actividad", "partida"], inplace=True)

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

        # Incluimos PA6 (ultimo ejercicio)
        if params.include_pa6:
            df = df.loc[df.ejercicio.astype(int) < int(params.ejercicio)]
            icaro_params = CargaFullFilter(
                query_filter="partida~42[1-2]{1}, tipo!=REG",
                ejercicio=str(params.ejercicio),
                limit=None,
            )
            df_last = pd.DataFrame(
                await self.icaro_service.acum_with_desc_siif(
                    params=icaro_params, groub_by=campos_agrupacion
                )
            )
            if not df_last.empty:
                df_last["ejercicio"] = df_last["ejercicio"].astype(int)
                df = pd.concat([df, df_last], axis=0, ignore_index=True)

        # Agregamos ejecución acumulada de Patricia
        if params.agregar_acum_2008:
            df_acum_2008 = pd.DataFrame(await self.planillometro_hist_repo.get_all())
            if not df_acum_2008.empty:
                df["estructura"] = df["actividad"] + "-" + df["partida"]
                df_acum_2008["ejercicio"] = 2008
                df_acum_2008["avance"] = 1
                df_acum_2008["desc_obra"] = df_acum_2008["desc_actividad"]
                df_acum_2008 = df_acum_2008.rename(columns={"acum_2008": "importe"})

                # --- 1. Extraer los códigos de la estructura en ambos DataFrames ---
                for dataframe in [df, df_acum_2008]:
                    if "estructura" in dataframe.columns:
                        partes = dataframe["estructura"].str.split("-", expand=True)
                        dataframe["cod_programa"] = partes[0]
                        dataframe["cod_subprograma"] = partes[1]
                        dataframe["cod_proyecto"] = partes[2]
                        dataframe["cod_actividad"] = partes[3]

                # --- 2. Crear Mappings de Descripciones de "df" por Código ---
                map_prog = (
                    df[["cod_programa", "desc_programa"]]
                    .dropna()
                    .drop_duplicates(subset=["cod_programa"])
                    .set_index("cod_programa")["desc_programa"]
                )

                map_proy = (
                    df[["cod_programa", "cod_proyecto", "desc_proyecto"]]
                    .dropna()
                    .drop_duplicates(subset=["cod_programa", "cod_proyecto"])
                    .set_index(["cod_programa", "cod_proyecto"])["desc_proyecto"]
                )

                map_act = (
                    df[
                        [
                            "cod_programa",
                            "cod_proyecto",
                            "cod_actividad",
                            "desc_actividad",
                        ]
                    ]
                    .dropna()
                    .drop_duplicates(
                        subset=["cod_programa", "cod_proyecto", "cod_actividad"]
                    )
                    .set_index(["cod_programa", "cod_proyecto", "cod_actividad"])[
                        "desc_actividad"
                    ]
                )

                if params.desagregar_desc_subprog:
                    map_subprog = (
                        df[["cod_programa", "cod_subprograma", "desc_subprograma"]]
                        .dropna()
                        .drop_duplicates(subset=["cod_programa", "cod_subprograma"])
                        .set_index(["cod_programa", "cod_subprograma"])[
                            "desc_subprograma"
                        ]
                    )

                # --- 3. Homogeneizar df_acum_2008 usando los Mappings de df ---

                # A. Programa (Clave simple)
                df_acum_2008["desc_programa"] = (
                    df_acum_2008["cod_programa"]
                    .map(map_prog)
                    .fillna(df_acum_2008["desc_programa"])
                )

                # B. Proyecto (Clave Compuesta: Tupla de Pandas)
                idx_proy = list(
                    zip(df_acum_2008["cod_programa"], df_acum_2008["cod_proyecto"])
                )
                df_acum_2008["desc_proyecto"] = (
                    pd.Series(idx_proy, index=df_acum_2008.index)
                    .map(map_proy)
                    .fillna(df_acum_2008["desc_proyecto"])
                )

                # C. Actividad (Clave Compuesta: Tupla de Pandas)
                idx_act = list(
                    zip(
                        df_acum_2008["cod_programa"],
                        df_acum_2008["cod_proyecto"],
                        df_acum_2008["cod_actividad"],
                    )
                )
                df_acum_2008["desc_actividad"] = (
                    pd.Series(idx_act, index=df_acum_2008.index)
                    .map(map_act)
                    .fillna(df_acum_2008["desc_actividad"])
                )

                # D. Subprograma (Opcional)
                if (
                    params.desagregar_desc_subprog
                    and "desc_subprograma" in df_acum_2008.columns
                ):
                    idx_sub = list(
                        zip(
                            df_acum_2008["cod_programa"],
                            df_acum_2008["cod_subprograma"],
                        )
                    )
                    df_acum_2008["desc_subprograma"] = (
                        pd.Series(idx_sub, index=df_acum_2008.index)
                        .map(map_subprog)
                        .fillna(df_acum_2008["desc_subprograma"])
                    )

                # --- 4. Limpieza de columnas temporales ---
                cols_aux = [c for c in df_acum_2008.columns if c.startswith("cod_")]
                df_acum_2008 = df_acum_2008.drop(columns=cols_aux, errors="ignore")
                df = df.drop(
                    columns=[c for c in df.columns if c.startswith("cod_")],
                    errors="ignore",
                )

                # --- 5. Unificación final ---
                df = pd.concat([df, df_acum_2008], ignore_index=True)
                df = df.drop(columns=["estructura"], errors="ignore")

        # --- OPTIMIZACIÓN CLAVE: Agrupación única ---
        # Obtenemos 'alta' (mínimo ejercicio) y 'acum' (suma de importe) por grupo + desc_obra
        df_prev_acum = df.loc[df["ejercicio"].astype(int) < int(params.ejercicio)]
        df_prev_acum = (
            df_prev_acum.groupby(group_cols + ["desc_obra"])
            .agg(
                acum=("importe", "sum"),
                alta=("ejercicio", "min"),
                avance=("avance", "max"),
            )
            .reset_index()
        )
        df_prev_acum["avance"] = df_prev_acum["avance"].fillna(0)
        df_prev_acum["en_curso_ant"] = df_prev_acum.loc[df_prev_acum["avance"] < 1][
            "acum"
        ]
        df_prev_acum["terminadas_ant"] = df_prev_acum.loc[df_prev_acum["avance"] == 1][
            "acum"
        ]
        df_prev_acum = df_prev_acum.drop(columns=["avance"], errors="ignore")

        # Limitamos df al ejercicio solicitado
        df = df.loc[df["ejercicio"].astype(int) == int(params.ejercicio)]
        df = (
            df.groupby(group_cols + ["desc_obra"])
            .agg(
                ejecucion=("importe", "sum"),
                avance=("avance", "max"),
            )
            .reset_index()
        )
        df["avance"] = df["avance"].fillna(0)
        df["en_curso_actual"] = df.loc[df["avance"] < 1]["ejecucion"]
        df["terminadas_actual"] = df.loc[df["avance"] == 1]["ejecucion"]
        df = df.drop(columns=["avance"], errors="ignore")

        # Join con df_prev_acum para obtener acumulados históricos y altas
        df = pd.merge(df, df_prev_acum, how="outer", on=group_cols + ["desc_obra"])
        fill_na_cols = [
            "ejecucion",
            "acum",
            "en_curso_ant",
            "terminadas_ant",
            "en_curso_actual",
            "terminadas_actual",
        ]
        df[fill_na_cols] = df[fill_na_cols].fillna(0)

        # Agregamos alta a las obras que empezaron en el ejercicio actual y no tienen alta previa
        df["alta"] = df["alta"].fillna(int(params.ejercicio))

        # Agregamos la ejecución actual al acum para obtener el acumulado final
        df["acum"] = df["acum"] + df["ejecucion"]

        # Generamos la columna en_curso real y ajustamos terminadas_actual
        # 1. Definimos la condición claramente una sola vez
        es_terminada = df["terminadas_actual"] > 0

        # 2. Ajustamos 'terminadas_actual' sumando el acumulado anterior
        df.loc[es_terminada, "terminadas_actual"] += df["en_curso_ant"]

        # 3. Calculamos 'en_curso' directo: si terminó, el saldo anterior pasa a ser 0
        df["en_curso"] = (
            np.where(es_terminada, 0, df["en_curso_ant"]) + df["en_curso_actual"]
        )

        # 4. Limpieza de columnas temporales
        df = df.drop(columns=["en_curso_ant", "en_curso_actual"], errors="ignore")

        # Agrupamos por última vez para consolidar por grupo y desc_obra
        df = (
            df.groupby(group_cols)
            .agg(
                alta=("alta", "min"),
                ejecucion=("ejecucion", "sum"),
                acum=("acum", "sum"),
                en_curso=("en_curso", "sum"),
                terminadas_ant=("terminadas_ant", "sum"),
                terminadas_actual=("terminadas_actual", "sum"),
            )
            .reset_index()
        )

        df["actividad"] = df["actividad"] + "-" + df["partida"]
        df.rename(columns={"actividad": "estructura"}, inplace=True)

        if not params.desagregar_partida:
            df.drop(columns=["partida"], inplace=True, errors="ignore")

        df.sort_values(["estructura"], ascending=[True], inplace=True)
        df["alta"] = df["alta"].astype("Int64").astype(str)

        ## Procedemos a agregar el campo ejercicio
        # Insertarla en la posición inmediatamente después de 'alta'
        posicion_alta = df.columns.get_loc("alta")
        df.insert(posicion_alta + 1, "ejercicio", int(params.ejercicio))

        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export_eecc(
        self, params: ReportePlanillometroLiteFilter
    ) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        icaro_params = ReportePlanillometroGenerateFilter(
            ejercicio=str(params.ejercicio),
            # ultimos_ejercicios=5,
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

    # -------------------------------------------------
    async def add_many(
        self, data: List[ReportePlanillometroReport]
    ) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ReportePlanillometroReport,
                field_id=[
                    "ejercicio",
                    "estructura",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 🔥 CONTROL CRÍTICO: Si no hay registros válidos, lanzamos un 400 Bad Request.
            # (Asumo que validation_result.validated es una lista vacía o None cuando falla todo)
            if not validation_result.validated:
                # Si validation_result tiene una lista de errores detallados, los exponemos al frontend
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    # Formateamos los primeros errores para no saturar el log pero dar contexto claro
                    detail_msg += f" Errores detectados: {validation_result.errors[:2]}"

                raise HTTPException(status_code=400, detail=detail_msg)

            # 2. Excluimos los campos None para que no se persistan como null en MongoDB
            # (las claves con valor None no se guardarán en los documentos)
            validation_result.validated = [
                record.model_dump(exclude_none=True)
                for record in validation_result.validated
            ]

            # 3. Determinar filtro de borrado (Idempotencia)
            # A esta altura ya es 100% seguro que al menos hay un registro válido en el índice [0]
            ejercicio_detectado = validation_result.validated[0]["ejercicio"]
            delete_filter = {"ejercicio": ejercicio_detectado}

            # 4. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Reporte Planillometro",
                label=f"Reporte Planillometro del Ejercicio {ejercicio_detectado}",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ReportePlanillometroLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ReportePlanillometroFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df_planillometro = pd.DataFrame(
            [d.model_dump(by_alias=True, mode="json") for d in data]
        )
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

        return self.export_to_excel(
            data_pairs=[
                (df_planillometro, "bd_planillometro"),
                # (sgv, "bd_recuperos"),
            ],
            filename="Reporte Planillometro.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1Hmb7xmzhZBoicnL5_tN7mr1kOj-r3gw8lCkPErR8Xd4",
        )

    # -------------------------------------------------
    async def unique_estructura(self) -> List[str]:
        """Devuelve las estructuras únicas de la colección.

        Usa el comando `distinct` de MongoDB para obtener las estructuras
        sin traer toda la colección a la memoria. Devuelve una lista plana
        de strings, lista para usar directamente como `options` de un
        `st.selectbox` en el frontend.
        """
        try:
            # collection es el AsyncIOMotorCollection expuesto por BaseRepository.
            valores = await self.repository.collection.distinct("estructura")

            # Filtramos valores vacíos/nulos y forzamos la unicidad (por si el
            # backend no la garantiza), luego ordenamos para devolver una lista
            # estable y predecible al frontend.
            return sorted({str(valor) for valor in valores if valor})
        except Exception as e:
            self._handle_error("Error obteniendo las estructuras únicas", e)


ReportePlanillometroServiceDependency = Annotated[
    ReportePlanillometroService, Depends()
]
