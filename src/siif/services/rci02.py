__all__ = ["Rci02Service", "Rci02ServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
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
from ..repositories import Rci02RepositoryDependency
from ..schemas import (
    Rci02Document,
    Rci02FullFilter,
    Rci02LiteFilter,
    Rci02Report,
    Rci02SummarizedReport,
)


@dataclass
# -------------------------------------------------
class Rci02Service(
    BaseService[Rci02Report, Rci02Document, Rci02FullFilter, Rci02LiteFilter]
):
    repository: Rci02RepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rci02FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rci02Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rci02Report,
                field_id="nro_entrada",  # O el campo que identifique la fila en caso de error
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
                title="Sincronización SIIF Rci02",
                label="Rci02",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rci02LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rci02FullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_Rci02")], filename="reporte_rci02.xlsx"
        )

    # -------------------------------------------------
    async def summarize(
        self,
        params: Rci02FullFilter,
        groub_by: List[str] = ["ejercicio", "mes", "cta_cte"],
    ) -> List[Rci02SummarizedReport]:

        # 1. Generamos el dict de filtro de MongoDB usando tu método existente
        mongo_query = params.get_full_filter()

        # 2. Definimos los campos de agrupación
        campos_agrupacion = groub_by

        # 3. Armamos el _id del $group y las proyecciones para el $project
        id_group = {col: f"${col}" for col in campos_agrupacion}
        projection = {col: f"$_id.{col}" for col in campos_agrupacion}
        projection.update({"_id": 0, "importe": 1})

        # 4. Pipeline de Agregación
        pipeline = [
            # ETAPA 1: Filtra la colección ANTES de agrupar (Cero desperdicio de CPU)
            {"$match": mongo_query},
            # ETAPA 2: Agrupa únicamente sobre el resultado del $match
            {
                "$group": {
                    "_id": id_group,
                    "importe": {"$sum": "$importe"},
                }
            },
            # ETAPA 3: Proyección limpia para Pandas
            {"$project": projection},
        ]

        # 5. Ejecución Asíncrona con Motor
        # .aggregate(pipeline) devuelve un cursor asíncrono
        cursor = self.repository.collection.aggregate(pipeline)

        # Traemos los documentos a una lista de Python de forma asíncrona
        # length=None trae todos los registros agregados (que ahora son solo ~3.200)
        documentos = await cursor.to_list(length=None)

        # 6. Convertimos a DataFrame de Pandas
        df = pd.DataFrame(documentos)

        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data


Rci02ServiceDependency = Annotated[Rci02Service, Depends()]
