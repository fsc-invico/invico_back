__all__ = ["SaldosBarriosEvolucionService", "SaldosBarriosEvolucionServiceDependency"]

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
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import SaldosBarriosEvolucionRepositoryDependency
from ..schemas import (
    SaldosBarriosEvolucionDocument,
    SaldosBarriosEvolucionFullFilter,
    SaldosBarriosEvolucionLiteFilter,
    SaldosBarriosEvolucionReport,
)


@dataclass
# -------------------------------------------------
class SaldosBarriosEvolucionService(
    BaseService[
        SaldosBarriosEvolucionReport,
        SaldosBarriosEvolucionDocument,
        SaldosBarriosEvolucionFullFilter,
        SaldosBarriosEvolucionLiteFilter,
    ]
):
    repository: SaldosBarriosEvolucionRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=SaldosBarriosEvolucionFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[SaldosBarriosEvolucionReport]
    ) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=SaldosBarriosEvolucionReport,
                field_id=[
                    "ejercicio",
                    "cod_barrio",
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
            delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SGV Saldos Barrios Evolución",
                label="Saldos Barrios Evolución",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(
        self, params: SaldosBarriosEvolucionLiteFilter
    ) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = SaldosBarriosEvolucionFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SGV_Saldos_Barrios_Evolucion")],
            filename="reporte_saldos_barrios_evolucion.xlsx",
        )

    # -------------------------------------------------
    async def unique_cod_barrios(self) -> List[str]:
        """Devuelve los códigos de barrio únicos de la colección.

        Usa el comando `distinct` de MongoDB para obtener los códigos
        sin traer toda la colección a la memoria. Devuelve una lista plana
        de strings, lista para usar directamente como `options` de un
        `st.selectbox` en el frontend.
        """
        try:
            # collection es el AsyncIOMotorCollection expuesto por BaseRepository.
            valores = await self.repository.collection.distinct("cod_barrio")

            # Filtramos valores vacíos/nulos y forzamos la unicidad (por si el
            # backend no la garantiza), luego ordenamos para devolver una lista
            # estable y predecible al frontend.
            return sorted({str(valor) for valor in valores if valor})
        except Exception as e:
            self._handle_error("Error obteniendo los códigos de barrio únicos", e)


SaldosBarriosEvolucionServiceDependency = Annotated[
    SaldosBarriosEvolucionService, Depends()
]
