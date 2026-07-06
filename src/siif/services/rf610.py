__all__ = ["Rf610Service", "Rf610ServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import Rf610RepositoryDependency
from ..schemas import (
    Rf610DescEstructuras,
    Rf610Document,
    Rf610FullFilter,
    Rf610LiteFilter,
    Rf610Report,
)


@dataclass
# -------------------------------------------------
class Rf610Service(
    BaseService[Rf610Report, Rf610Document, Rf610FullFilter, Rf610LiteFilter]
):
    repository: Rf610RepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rf610FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rf610Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            # Usamos Rf610Report o Rf610Document para validar cada fila
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rf610Report,
                field_id="estructura",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RF610",
                label="RF610",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rf610LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rf610FullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RF610")], filename="reporte_rf610.xlsx"
        )

    # -------------------------------------------------
    async def desc_estructuras(
        self, params: Rf610FullFilter
    ) -> List[Rf610DescEstructuras]:
        data = await self.repository.find_with_filter_params(params=params)

        # 🔥 LA VALIDACIÓN: Si no viene nada de la base de datos, cortamos acá
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros de Estructuras en SIIF's RF610 para el ejercicio o filtros seleccionados.",
            )

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])

        df.sort_values(
            by=["ejercicio", "estructura"], inplace=True, ascending=[False, True]
        )
        # Programas únicos
        df_prog = df.loc[:, ["programa", "desc_programa"]]
        df_prog.drop_duplicates(subset=["programa"], inplace=True, keep="first")
        # Subprogramas únicos
        df_subprog = df.loc[:, ["programa", "subprograma", "desc_subprograma"]]
        df_subprog.drop_duplicates(
            subset=["programa", "subprograma"], inplace=True, keep="first"
        )
        # Proyectos únicos
        df_proy = df.loc[:, ["programa", "subprograma", "proyecto", "desc_proyecto"]]
        df_proy.drop_duplicates(
            subset=["programa", "subprograma", "proyecto"], inplace=True, keep="first"
        )
        # Actividades únicos
        # Reemplazar los NaN por una cadena vacía en la columna 'desc_actividad'
        df["desc_actividad"] = df["desc_actividad"].fillna("")

        df_act = df.loc[
            :,
            [
                "estructura",
                "programa",
                "subprograma",
                "proyecto",
                "actividad",
                "desc_actividad",
            ],
        ]

        df_act.drop_duplicates(subset=["estructura"], inplace=True, keep="first")
        # Merge all
        df = df_act.merge(df_prog, how="left", on="programa")
        df = df.merge(df_subprog, how="left", on=["programa", "subprograma"])
        df = df.merge(df_proy, how="left", on=["programa", "subprograma", "proyecto"])
        df["desc_programa"] = df.programa + " - " + df.desc_programa
        df["desc_subprograma"] = df.subprograma + " - " + df.desc_subprograma
        df["desc_proyecto"] = df.proyecto + " - " + df.desc_proyecto
        df["desc_actividad"] = df.actividad + " - " + df.desc_actividad
        df.drop(
            labels=["programa", "subprograma", "proyecto", "actividad"],
            axis=1,
            inplace=True,
        )
        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data


Rf610ServiceDependency = Annotated[Rf610Service, Depends()]
