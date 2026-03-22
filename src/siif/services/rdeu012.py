__all__ = ["Rdeu012Service", "Rdeu012ServiceDependency"]

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
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import Rdeu012RepositoryDependency
from ..schemas import (
    Rdeu012Document,
    Rdeu012FullFilter,
    Rdeu012LiteFilter,
    Rdeu012Report,
)


@dataclass
# -------------------------------------------------
class Rdeu012Service(
    BaseService[Rdeu012Report, Rdeu012Document, Rdeu012FullFilter, Rdeu012LiteFilter]
):
    repository: Rdeu012RepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=Rdeu012FullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[Rdeu012Report]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=Rdeu012Report,
                field_id=[
                    "mes_hasta",
                    "nro_comprobante",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                mes_hasta_detectado = validation_result.validated[0].mes_hasta
                delete_filter = {"mes_hasta": mes_hasta_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SIIF RDEU012",
                label="RDEU012",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: Rdeu012LiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = Rdeu012FullFilter(
            query_filter=params.query_filter,
            mesAño=params.mes_hasta,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SIIF_RDEU012")], filename="reporte_rdeu012.xlsx"
        )


Rdeu012ServiceDependency = Annotated[Rdeu012Service, Depends()]
