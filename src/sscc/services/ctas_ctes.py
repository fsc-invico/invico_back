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
    async def cta_cte_unifier(self, original_df: pd.DataFrame, cta_cte_nexo: str):
        """
        Map cta_cte in original_df to map_to in Ctas Ctes collection using cta_cte_nexo
        """
        if not original_df.empty:
            ctas_ctes = pd.DataFrame(await self.repository.get_all())
            if not ctas_ctes.empty:
                map_to = ctas_ctes.loc[:, ["map_to", cta_cte_nexo]]
                df = pd.merge(
                    original_df,
                    map_to,
                    how="left",
                    left_on="cta_cte",
                    right_on=cta_cte_nexo,
                )
                df["cta_cte"] = df["map_to"]
                df.drop(["map_to", cta_cte_nexo], axis="columns", inplace=True)
            else:
                df = original_df

        return df.to_dict(orient="records")


CtasCtesServiceDependency = Annotated[CtasCtesService, Depends()]
