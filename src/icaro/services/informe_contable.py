__all__ = ["InformeContableService", "InformeContableServiceDependency"]

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import InformeContableRepositoryDependency
from ..schemas import (
    InformeContableDocument,
    InformeContableFullFilter,
    InformeContableLiteFilter,
    InformeContableReport,
)


@dataclass
# -------------------------------------------------
class InformeContableService(
    BaseService[
        InformeContableReport,
        InformeContableDocument,
        InformeContableFullFilter,
        InformeContableLiteFilter,
    ]
):
    repository: InformeContableRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=InformeContableFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[InformeContableReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=InformeContableReport,
                field_id=[
                    "beneficiario",
                    "desc_obra",
                    "nro_certificado",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            # delete_filter = {}
            delete_filter = {"id_carga": {"$in": ["", None]}}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO CERTIFICADOS",
                label="CERTIFICADOS",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: InformeContableLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = InformeContableFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_CERTIFICADOS")],
            filename="reporte_icaro_certificados.xlsx",
        )

    # -------------------------------------------------
    async def update_id_carga(self, id: str, id_carga: str) -> InformeContableDocument:
        try:
            # 1. Preparamos los datos de actualización
            update_data = {
                "id_carga": id_carga,
                "updated_at": datetime.now(timezone.utc),
            }

            # 2. Llamamos al repositorio (suponiendo que tenés un update genérico)
            # o usamos find_one_and_update directamente
            updated_doc = await self.repository.update_by_id(id, update_data)

            if not updated_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No se encontró el registro con ID {id}",
                )

            return updated_doc

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al actualizar id_carga: {str(e)}")
            self._handle_error("Error técnico al actualizar el vínculo de carga", e)

    # -------------------------------------------------
    async def unlink_carga_value(self, id_carga: str):
        try:
            # Buscamos el documento que tiene ese id_carga y lo seteamos en ""
            update_data = {"id_carga": "", "updated_at": datetime.now(timezone.utc)}

            # Usamos update_many por si las dudas hubiera más de uno,
            # aunque lo normal es que sea uno solo.
            modificados = await self.repository.update_many(
                {"id_carga": id_carga}, update_data
            )
            if modificados > 0:
                logger.info(f"Se actualizaron {modificados} registros.")

            return {"status": "updated", "modified_count": modificados}
        except Exception as e:
            self._handle_error(f"Error al desvincular el id_carga {id_carga}", e)


InformeContableServiceDependency = Annotated[InformeContableService, Depends()]
