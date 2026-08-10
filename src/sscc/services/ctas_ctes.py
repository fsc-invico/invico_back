__all__ = ["CtasCtesService", "CtasCtesServiceDependency"]

from dataclasses import dataclass
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import CtasCtesRepositoryDependency
from ..schemas import (
    CtasCtesDocument,
    CtasCtesFullFilter,
    CtasCtesLiteFilter,
    CtasCtesReport,
)


@dataclass
# -------------------------------------------------
class CtasCtesService(
    BaseService[
        CtasCtesReport,
        CtasCtesDocument,
        CtasCtesFullFilter,
        CtasCtesLiteFilter,
    ]
):
    repository: CtasCtesRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=CtasCtesFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[CtasCtesReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=CtasCtesReport,
                field_id="map_to",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SSCC Ctas Ctes",
                label="Ctas Ctes",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: CtasCtesLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = CtasCtesFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "Ctas Ctes")], filename="reporte_ctas_ctes.xlsx"
        )

    # --------------------------------------------------
    async def cta_cte_unifier(
        self, original_df: pd.DataFrame, cta_cte_nexo: str
    ) -> pd.DataFrame:
        """
        Mapea la columna 'cta_cte' en original_df hacia 'map_to' de la colección Ctas Ctes
        usando la columna nexo indicada.

        Returns:
            pd.DataFrame con la columna 'cta_cte' unificada.
        """
        if original_df.empty:
            return original_df

        # 1. Obtenemos los documentos (idealmente solo con la proyección de las dos claves)
        cursor = self.repository.collection.find(
            {cta_cte_nexo: {"$exists": True, "$ne": None}},
            {"map_to": 1, cta_cte_nexo: 1, "_id": 0},
        )
        ctas_ctes_raw = await cursor.to_list(length=None)

        if not ctas_ctes_raw:
            return original_df

        # 2. Armamos el diccionario clave-valor directamente en Python
        # { "cta_cte_origen": "map_to_destino" }
        mapping_dict = {
            doc[cta_cte_nexo]: doc["map_to"]
            for doc in ctas_ctes_raw
            if cta_cte_nexo in doc and "map_to" in doc
        }

        # 3. Mapeamos en el DataFrame principal
        df = original_df.copy()
        mapped_values = df["cta_cte"].map(mapping_dict)
        df["cta_cte"] = mapped_values.fillna(df["cta_cte"])

        return df


CtasCtesServiceDependency = Annotated[CtasCtesService, Depends()]
