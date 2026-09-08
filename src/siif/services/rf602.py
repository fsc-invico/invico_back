__all__ = ["Rf602Service", "Rf602ServiceDependency"]

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
from ..repositories import Rf602RepositoryDependency
from ..schemas import (
    Rf602Document,
    Rf602FullFilter,
    Rf602LiteFilter,
    Rf602Report,
    Rf602WithDescEstructuras,
)
from ..services.rf610 import Rf610ServiceDependency


@dataclass
# -------------------------------------------------
class Rf602Service(
    BaseService[Rf602Report, Rf602Document, Rf602FullFilter, Rf602LiteFilter]
):
    repository: Rf602RepositoryDependency
    rf610_service: Rf610ServiceDependency  # Dependencia del servicio RF610 para obtener descripciones

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rf602FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rf602Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            # Usamos Rf602Report o Rf602Document para validar cada fila
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rf602Report,
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
                title="Sincronización SIIF RF602",
                label="RF602",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rf602LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rf602FullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RF602")], filename="reporte_rf602.xlsx"
        )

    # -------------------------------------------------
    async def with_desc_estructuras(
        self, params: Rf602FullFilter
    ) -> List[Rf602WithDescEstructuras]:
        data = await self.repository.find_with_filter_params(params=params)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros de Estructuras en SIIF's RF602 para el ejercicio o filtros seleccionados.",
            )

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        df = df.sort_values(by=["ejercicio", "estructura"], ascending=[False, True])

        rf610_df = pd.DataFrame(
            await self.rf610_service.desc_estructuras(params=params)
        )
        if not rf610_df.empty:
            df = df.merge(rf610_df, how="left", on="estructura")
        # df.drop(
        #     labels=[
        #         "org",
        #         "pendiente",
        #         "subprograma",
        #         "proyecto",
        #         "actividad",
        #     ],
        #     axis=1,
        #     inplace=True,
        # )

        # df["programa"] = df["programa"].astype(int)
        # df["fuente"] = df["fuente"].astype(int)

        # first_cols = [
        #     "ejercicio",
        #     "estructura",
        #     "partida",
        #     "fuente",
        #     "desc_programa",
        #     "desc_subprograma",
        #     "desc_proyecto",
        #     "desc_actividad",
        #     "programa",
        #     "grupo",
        # ]
        # df = df.loc[:, first_cols].join(df.drop(first_cols, axis=1))

        df = pd.DataFrame(df)
        df.reset_index(drop=True, inplace=True)
        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data

    # -------------------------------------------------
    async def group_projection(
        self,
        params: Rf602FullFilter,
        group_by: list = ["ejercicio", "programa"],  # Grupo se incluye por defecto,
    ) -> List[dict]:

        # 1. Generamos el dict de filtro de MongoDB usando tu método existente
        mongo_query = params.get_full_filter()

        # 2. Armamos el _id del $group y las proyecciones para el $project
        # Construimos el _id combinando los campos pasados + grupo_calculado
        id_group = {col: f"${col}" for col in group_by}
        id_group["grupo"] = "$grupo_calculado"

        # 3. Armamos la proyección dinámica mapeando desde $_id
        projection = {col: f"$_id.{col}" for col in group_by}
        projection["grupo"] = "$_id.grupo"
        projection["_id"] = 0
        projection["ordenado"] = 1

        # 4. Pipeline de Agregación
        pipeline = [
            # ETAPA 1: Filtra la colección ANTES de agrupar (Cero desperdicio de CPU)
            {"$match": mongo_query},
            # ETAPA 2: Normalización/Clasificación de la partida únicamente para el grupo 400
            {
                "$addFields": {
                    "grupo_calculado": {
                        "$cond": {
                            "if": {"$eq": ["$grupo", "400"]},
                            "then": {
                                "$switch": {
                                    "branches": [
                                        {
                                            "case": {"$eq": ["$partida", "411"]},
                                            "then": "411",
                                        },
                                        {
                                            "case": {"$eq": ["$partida", "421"]},
                                            "then": "421",
                                        },
                                        {
                                            "case": {"$eq": ["$partida", "422"]},
                                            "then": "422",
                                        },
                                    ],
                                    "default": "resto_400",
                                }
                            },
                            "else": "$grupo",
                        }
                    }
                }
            },
            # ETAPA 3: Agrupa únicamente sobre el resultado del $match
            {
                "$group": {
                    "_id": id_group,
                    "ordenado": {"$sum": "$ordenado"},
                }
            },
            # ETAPA 4: Proyección limpia para Pandas
            {"$project": projection},
        ]

        # 5. Ejecución Asíncrona con Motor
        # .aggregate(pipeline) devuelve un cursor asíncrono
        cursor = self.repository.collection.aggregate(pipeline)

        # Traemos los documentos a una lista de Python de forma asíncrona
        # length=None trae todos los registros agregados (que ahora son solo ~3.200)
        documentos = await cursor.to_list(length=None)

        if not documentos:
            return []

        return documentos


Rf602ServiceDependency = Annotated[Rf602Service, Depends()]
