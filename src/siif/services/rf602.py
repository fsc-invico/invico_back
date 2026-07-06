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


Rf602ServiceDependency = Annotated[Rf602Service, Depends()]
