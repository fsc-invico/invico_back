__all__ = ["ControlObrasService", "ControlObrasServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...icaro.repositories import CargaRepositoryDependency
from ...sgf.schemas import ResumenRendProvFullFilter
from ...sgf.services import ResumenRendProvServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ControlObrasRepositoryDependency
from ..schemas import (
    ControlObrasDocument,
    ControlObrasFullFilter,
    ControlObrasLiteFilter,
    ControlObrasReport,
)


@dataclass
# -------------------------------------------------
class ControlObrasService(
    BaseService[
        ControlObrasReport,
        ControlObrasDocument,
        ControlObrasFullFilter,
        ControlObrasLiteFilter,
    ]
):
    ctrl_obras: ControlObrasRepositoryDependency
    resumen_rend_service: ResumenRendProvServiceDependency
    icaro_repo: CargaRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.ctrl_obras,
            filter_schema=ControlObrasFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ControlObrasReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlObrasReport,
                field_id=[
                    "mes",
                    "cta_cte",
                    "cuit",
                ],  # O el campo que identifique la fila en caso de error
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
                repository=self.ctrl_obras,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Obras",
                label="Control Obras",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ControlObrasLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        ctrl_obras_params = ControlObrasFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        resumen_rend_params = ResumenRendProvFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
            origen=None,
        )

        # 2. Traemos los datos sin paginar
        data_ctrl_obras = await self.ctrl_obras.find_with_filter_params(
            params=ctrl_obras_params
        )
        data_sgf = await self.resumen_rend_service.unique_obras(
            params=resumen_rend_params
        )
        data_icaro = await self.icaro_repo.find_with_filter_params(
            params=ctrl_obras_params
        )

        # 3. Usar el método de la clase base
        df_ctrl_obras = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_obras]
        )
        df_sgf = pd.DataFrame(data_sgf)
        df_icaro = pd.DataFrame([d.model_dump(by_alias=True) for d in data_icaro])
        return self.export_to_excel(
            data_pairs=[
                (df_ctrl_obras, "control_mes_cta_cte_cuit_db"),
                (df_sgf, "resumen_rend_cuit"),
                (df_icaro, "icaro_carga_neto_rdeu"),
            ],
            filename="Control Obras.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="16v2ovmQnS1v73-WxTOK6b9Tx9DRugGc70ufpjVi-rPA",
        )


ControlObrasServiceDependency = Annotated[ControlObrasService, Depends()]
