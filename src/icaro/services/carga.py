__all__ = ["CargaService", "CargaServiceDependency"]

# import os
from dataclasses import dataclass
from datetime import datetime, timezone

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
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import CargaRepositoryDependency
from ..schemas import CargaDocument, CargaFullFilter, CargaLiteFilter, CargaReport


@dataclass
# -------------------------------------------------
class CargaService(
    BaseService[CargaReport, CargaDocument, CargaFullFilter, CargaLiteFilter]
):
    repository: CargaRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        self.repository.unique_field = (
            "id_carga"  # Asegúrate de que tu repositorio sepa cuál es el campo único
        )
        super().__init__(
            repository=self.repository,
            filter_schema=CargaFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_one(self, data: CargaReport) -> CargaDocument:
        """
        Inserta un único registro verificando que el id_carga no exista.
        """
        try:
            # 1. Verificar si ya existe un registro con ese id_carga
            # Usamos el repositorio para buscar por el campo único
            return await self.repository.save(data)

        except Exception as e:
            logger.error(f"Error en add_one: {str(e)}")
            self._handle_error("Error durante el proceso de add_one", e)

    # -------------------------------------------------
    async def add_many(self, data: List[CargaReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=CargaReport,
                field_id="id_carga",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            # if validation_result.validated:
            #     # Tomamos el ejercicio del primer registro válido
            #     ejercicio_detectado = validation_result.validated[0].ejercicio
            #     delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO CARGA",
                label="CARGA",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: CargaLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = CargaFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_CARGA")], filename="reporte_icaro_carga.xlsx"
        )

    # -------------------------------------------------
    async def update_one_safely(self, id: str, data: CargaReport) -> CargaDocument:
        try:
            post_id = CargaDocument.validate_id(id)
            new_timestamp = datetime.now(timezone.utc)
            
            # 1. VERIFICACIÓN DE ID_CARGA DUPLICADO
            # Buscamos si existe otro documento con ese id_carga que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields({
                "id_carga": data.id_carga,
                "_id": {"$ne": post_id} 
            })
            
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: El ID de Carga '{data.id_carga}' ya está siendo usado por otro comprobante."
                )

            # 2. INTENTO DE ACTUALIZACIÓN (Control de Concurrencia)
            new_data = data.model_dump(by_alias=True)
            new_data["updated_at"] = new_timestamp

            updated_doc = await self.repository.find_one_and_update(
                filter={
                    "_id": post_id, 
                    "updated_at": data.updated_at # El cerrojo
                },
                update_data=new_data,
                return_document=True
            )

            if not updated_doc:
                # Si llegamos acá es porque el ID no existe o el updated_at cambió (Conflicto)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflicto de edición: Los datos fueron modificados por otro usuario. Por favor, recargue la página."
                )

            return self.model(**updated_doc)
        
        except Exception as e:
            logger.error(f"Error en update_one_safely: {str(e)}")
            self._handle_error("Error durante el proceso de update_one_safely", e)



CargaServiceDependency = Annotated[CargaService, Depends()]
