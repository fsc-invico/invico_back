__all__ = ["Rcocc31Service", "Rcocc31ServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException
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
from ..repositories import Rcocc31RepositoryDependency
from ..schemas import (
    Rcocc31Document,
    Rcocc31FullFilter,
    Rcocc31LiteFilter,
    Rcocc31Report,
    Rcocc31SummarizedReport,
)


@dataclass
# -------------------------------------------------
class Rcocc31Service(
    BaseService[Rcocc31Report, Rcocc31Document, Rcocc31FullFilter, Rcocc31LiteFilter]
):
    repository: Rcocc31RepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rcocc31FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rcocc31Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            # Usamos Rf602Report o Rf602Document para validar cada fila
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rcocc31Report,
                field_id=[
                    "cta_contable",
                    "nro_entrada",
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

            # 2. Determinar filtro de borrado (Idempotencia)
            # A esta altura ya es 100% seguro que al menos hay un registro válido en el índice [0]
            ejercicio_detectado = validation_result.validated[0].ejercicio
            cta_contable_detectada = validation_result.validated[0].cta_contable
            delete_filter = {
                "ejercicio": ejercicio_detectado,
                "cta_contable": cta_contable_detectada,
            }

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RCOCC31",
                label=f"RCOCC31 de la Cta Contable {cta_contable_detectada} y del Ejercicio {ejercicio_detectado}",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rcocc31LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rcocc31FullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            cta_contable=params.cta_contable,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RCOCC31")], filename="reporte_rcocc31.xlsx"
        )

    # -------------------------------------------------
    async def summarize(
        self,
        params: Rcocc31FullFilter,
        groub_by: List[str] = ["ejercicio", "mes", "cta_contable"],
    ) -> List[Rcocc31SummarizedReport]:

        # 1. Generamos el dict de filtro de MongoDB usando tu método existente
        mongo_query = params.get_full_filter()
        print(
            f"MongoDB Query: {mongo_query}"
        )  # Para depuración, puedes eliminarlo después

        # 2. Definimos los campos de agrupación
        campos_agrupacion = groub_by

        # 3. Armamos el _id del $group y las proyecciones para el $project
        id_group = {col: f"${col}" for col in campos_agrupacion}
        projection = {col: f"$_id.{col}" for col in campos_agrupacion}
        projection.update({"_id": 0, "creditos": 1, "debitos": 1, "saldo": 1})

        # 4. Pipeline de Agregación
        pipeline = [
            # ETAPA 1: Filtra la colección ANTES de agrupar (Cero desperdicio de CPU)
            {"$match": mongo_query},
            # ETAPA 2: Agrupa únicamente sobre el resultado del $match
            {
                "$group": {
                    "_id": id_group,
                    "creditos": {"$sum": "$creditos"},
                    "debitos": {"$sum": "$debitos"},
                    "saldo": {"$sum": "$saldo"},
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


Rcocc31ServiceDependency = Annotated[Rcocc31Service, Depends()]
