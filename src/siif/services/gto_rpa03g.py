__all__ = ["GtoRpa03gService", "GtoRpa03gServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import numpy as np
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
from ..repositories import Rpa03gRepositoryDependency
from ..schemas import (
    GtoRpa03gDocument,
    GtoRpa03gFullFilter,
    GtoRpa03gLiteFilter,
    GtoRpa03gReport,
)


@dataclass
# -------------------------------------------------
class GtoRpa03gService(
    BaseService[
        GtoRpa03gReport, GtoRpa03gDocument, GtoRpa03gFullFilter, GtoRpa03gLiteFilter
    ]
):
    repository: Rpa03gRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=GtoRpa03gFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[GtoRpa03gReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=GtoRpa03gReport,
                field_id="nro_comprobante",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                grupo_detectado = validation_result.validated[0].grupo
                delete_filter = {
                    "ejercicio": ejercicio_detectado,
                    "grupo": grupo_detectado,
                }

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RPA03G",
                label="RPA03G",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: GtoRpa03gLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = GtoRpa03gFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            grupo=params.grupo,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RPA03G")], filename="reporte_rpa03g.xlsx"
        )

    # -------------------------------------------------
    async def get_joined_with_rcg01_uejp(
        self,
        params: GtoRpa03gFullFilter,  # O el filtro que corresponda a retenciones
    ) -> List[dict]:

        # 1. Filtro generado a partir de los parámetros de retenciones
        mongo_query = params.get_full_filter()

        # 2. Pipeline de Agregación partiendo desde 'retenciones'
        pipeline = [
            # ETAPA 1: Filtramos la colección 'retenciones' primero
            {"$match": mongo_query},
            # ETAPA 2: Join con la colección 'carga'
            {
                "$lookup": {
                    "from": "siif_rcg01_uejp",  # Colección destino
                    "localField": "nro_comprobante",  # Campo origen
                    "foreignField": "nro_comprobante",  # Campo destino
                    "as": "temp_info",  # Nombre temporal del array
                }
            },
            # ETAPA 3: Aplanamos el array 'carga_info'.
            # Como es una relación N:1, convierte el array de 1 elemento en un objeto plano.
            # preserveNullAndEmptyArrays=True mantiene el registro aunque foreignField no exista en destino.
            {
                "$unwind": {
                    "path": "$temp_info",
                    "preserveNullAndEmptyArrays": True,
                }
            },
            # ETAPA 4: Proyección limpia para enviar directamente a Pandas
            {
                "$project": {
                    "_id": 0,
                    # Campos de la colección 'origen'
                    "ejercicio": 1,
                    "mes": 1,
                    "fecha": 1,
                    "nro_comprobante": 1,
                    "importe": 1,
                    "grupo": 1,
                    "partida": 1,
                    "nro_entrada": 1,
                    "nro_origen": 1,
                    "nro_expte": 1,
                    "glosa": 1,
                    "beneficiario": 1,
                    # Campos extraídos del documento coincidente de destino
                    "importe_total": "$temp_info.importe",
                    "fuente": "$temp_info.fuente",
                    "cta_cte": "$temp_info.cta_cte",
                    "cuit": "$temp_info.cuit",
                    "nro_fondo": "$temp_info.nro_fondo",
                    "clase_reg": "$temp_info.clase_reg",
                    "clase_mod": "$temp_info.clase_mod",
                    "clase_gto": "$temp_info.clase_gto",
                    "es_comprometido": "$temp_info.es_comprometido",
                    "es_verificado": "$temp_info.es_verificado",
                    "es_aprobado": "$temp_info.es_aprobado",
                    "es_pagado": "$temp_info.es_pagado",
                }
            },
        ]

        # 3. Ejecución Asíncrona con Motor sobre el repositorio de retenciones
        cursor = self.repository.collection.aggregate(pipeline)
        documentos = await cursor.to_list(length=None)

        if not documentos:
            return []

        # 4. Carga a Pandas y sanitización para respuesta JSON limpia
        df = pd.DataFrame(documentos)

        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        df = sanitize_dataframe_for_json_with_datetime(df)

        # df = df.loc[
        #     :,
        #     [
        #         "ejercicio",
        #         "mes",
        #         "fecha",
        #         "id_carga",
        #         "nro_comprobante",
        #         "tipo",
        #         "fuente",
        #         "actividad",
        #         "partida",
        #         "cta_cte",
        #         "cuit",
        #         "codigo",
        #         "importe",
        #         "importe_bruto",
        #         "desc_obra",
        #     ],
        # ]

        # Prevenimos errores de serialización sustituyendo NaN por None (null en JSON)
        return df.replace({np.nan: None}).to_dict(orient="records")


GtoRpa03gServiceDependency = Annotated[GtoRpa03gService, Depends()]
