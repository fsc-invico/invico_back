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
    @staticmethod
    def _cta_cte_es_usable(valor: object) -> bool:
        """True si el valor representa una cuenta real para cruzar.

        Descarta ``None``/NaN (ausencia de dato), strings vacíos y el
        literal ``"NA"`` (case-insensitive), que no identifican ninguna
        cuenta corriente.
        """
        if valor is None or pd.isna(valor):
            return False
        texto = str(valor).strip()
        return texto != "" and texto.upper() != "NA"

    # --------------------------------------------------
    async def cta_cte_unifier(
        self, original_df: pd.DataFrame, cta_cte_nexo: str
    ) -> pd.DataFrame:
        """
        Mapea la columna 'cta_cte' en original_df hacia 'map_to' de la
        colección Ctas Ctes usando la columna nexo indicada.

        Reglas (alineadas con ``cta_cte_unifier`` del frontend):

        - Los documentos se leen ordenados por ``_id`` asc y ante
          duplicados del mismo nexo gana el **primero** (paridad con
          ``drop_duplicates(keep="first")`` del front, que recibe la
          colección ordenada por ``_id``).
        - Se descartan del mapping los nexo/``map_to`` ausentes, vacíos
          o ``"NA"``: no identifican una cuenta real para cruzar.
        - **Si no hay match, o el match traería un valor vacío/``"NA"``,
          se conserva la ``cta_cte`` que trae el dataframe original**:
          nunca se pisa el dato de origen con basura.

        Args:
            original_df: DataFrame con la columna ``cta_cte`` a unificar.
            cta_cte_nexo: Campo nexo de la colección Ctas Ctes (p.ej.
                ``icaro_cta_cte``, ``sgf_cta_cte``).

        Returns:
            Copia de ``original_df`` con ``cta_cte`` unificada. Si el
            DataFrame está vacío o no tiene la columna ``cta_cte``, se
            devuelve tal cual.
        """
        if original_df.empty or "cta_cte" not in original_df.columns:
            return original_df

        # 1. Obtenemos los documentos (solo las claves) en el mismo
        #    orden que ve el frontend (API: sort_by=_id asc).
        cursor = self.repository.collection.find(
            {cta_cte_nexo: {"$exists": True, "$ne": None}},
            {"map_to": 1, cta_cte_nexo: 1, "_id": 0},
        ).sort("_id", 1)
        ctas_ctes_raw = await cursor.to_list(length=None)

        if not ctas_ctes_raw:
            return original_df

        # 2. Diccionario {cta_cte_origen: map_to_destino}. Prioriza el
        #    primer documento (keep="first" del front) y omite claves o
        #    valores vacíos/"NA"/nulos: no aportan un cruce válido.
        mapping_dict: dict[object, object] = {}
        for doc in ctas_ctes_raw:
            origen = doc.get(cta_cte_nexo)
            destino = doc.get("map_to")
            if not self._cta_cte_es_usable(origen) or not self._cta_cte_es_usable(
                destino
            ):
                continue
            mapping_dict.setdefault(origen, destino)

        if not mapping_dict:
            return original_df

        # 3. Mapeamos conservando el valor original cuando no hay match
        #    o cuando el match traería vacío/"NA".
        df = original_df.copy()
        valores_originales = df["cta_cte"].copy()
        mapeados = df["cta_cte"].map(mapping_dict)
        mapeado_str = mapeados.where(mapeados.notna(), "").astype(str).str.strip()
        match_valido = mapeado_str.ne("") & mapeado_str.str.upper().ne("NA")
        df["cta_cte"] = mapeados.where(match_valido, valores_originales)

        return df


CtasCtesServiceDependency = Annotated[CtasCtesService, Depends()]
