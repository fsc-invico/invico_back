__all__ = ["CtasCtesService", "CtasCtesServiceDependency"]

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, List

import pandas as pd
from bson import ObjectId
from fastapi import Depends, HTTPException, status
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


# --------------------------------------------------
def _normalize_lock_timestamp(value: datetime) -> datetime:
    """Normaliza un timestamp cerrojo a UTC aware con precisión de milisegundos.

    MongoDB almacena fechas en UTC con precisión de milisegundos y Motor las
    devuelve naive (sin tz). Para comparar el valor enviado por el front con el
    guardado en BD, ambos se convierten a UTC y se truncan los microsegundos.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


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
    async def add_one(self, cta_cte: CtasCtesReport) -> CtasCtesDocument:
        """Alta individual de una cuenta corriente.

        El cerrojo ``updated_at`` se asigna en el servidor cuando el
        payload no lo trae (paridad con ``ObrasRecuperadasService``).

        Args:
            cta_cte: Registro a dar de alta.

        Returns:
            Documento creado con el ``id`` asignado por MongoDB.

        Raises:
            HTTPException: 400 ante errores de validación; 500 ante
                cualquier otro fallo inesperado.
        """
        try:
            # El cerrojo de edición se asigna en el servidor al crear
            if cta_cte.updated_at is None:
                cta_cte.updated_at = datetime.now(timezone.utc)
            # Invocamos save_one que ya maneja la conversión a dict
            nueva_cta_cte = await self.repository.save_one(cta_cte)
            return nueva_cta_cte
        except ValueError as e:
            self._handle_error("Error de validación", e, status_code=400)
        except Exception as e:
            self._handle_error("Error inesperado en el servidor", e)

    # -------------------------------------------------
    async def update_one_safely(
        self, id: str, data: CtasCtesReport
    ) -> CtasCtesDocument:
        """Actualización con cerrojo de concurrencia optimista.

        Paridad estricta con
        ``ObrasRecuperadasService.update_one_safely``: 404 si el
        registro ya no existe, 409 ante conflictos de ``updated_at`` y
        re-chequeo atómico del cerrojo en la actualización. Los
        registros históricos sin ``updated_at`` en BD se actualizan sin
        control de concurrencia.

        Args:
            id: Identificador ``_id`` del registro a editar.
            data: Nuevos valores; debe traer el ``updated_at``
                original leído en el GET.

        Returns:
            Documento actualizado.

        Raises:
            HTTPException: 404 si no existe, 409 si hay conflicto de
                cerrojo, 500 ante fallos inesperados.
        """
        try:
            mongo_id = ObjectId(id)

            # 1. EXISTENCIA DEL REGISTRO (distingue 404 de 409)
            current_doc = await self.repository.get_by_id(mongo_id)
            if not current_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "La Cuenta Corriente ya no existe "
                        "(fue eliminada o re-sincronizada). "
                        "Recargue la página."
                    ),
                )

            db_lock = current_doc.get("updated_at")

            # 2. CERROJO AUSENTE EN LA BD (registro antiguo sin timestamp):
            #    no hay con qué comparar, se procede sin cerrojo.
            if db_lock is None:
                logger.warning(
                    f"update_one_safely: registro {id} sin updated_at en BD; "
                    "se omite el control de concurrencia."
                )
            else:
                # 3. CERROJO AUSENTE EN EL PAYLOAD (estricto):
                #    el front debe reenviar el updated_at original del registro.
                if data.updated_at is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "No se recibió 'updated_at': el front debe enviar "
                            "el valor original del registro para evitar "
                            "conflictos de edición."
                        ),
                    )

                # 4. COMPARACIÓN NORMALIZADA (UTC + precisión de milisegundos)
                received_lock = _normalize_lock_timestamp(data.updated_at)
                stored_lock = _normalize_lock_timestamp(db_lock)
                if received_lock != stored_lock:
                    logger.warning(
                        f"update_one_safely: conflicto de cerrojo en registro "
                        f"{id}. Recibido={data.updated_at!r} | BD={db_lock!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Conflicto de edición: Los datos fueron modificados "
                            "por otro usuario. Por favor, recargue la página."
                        ),
                    )

            # 5. INTENTO DE ACTUALIZACIÓN (re-chequeo atómico del cerrojo)
            new_data = data.model_dump(by_alias=True)
            new_data["updated_at"] = datetime.now(timezone.utc)

            update_filter: dict = {"_id": mongo_id}
            if db_lock is not None:
                # Valor crudo de la BD: coincidencia exacta en Mongo
                update_filter["updated_at"] = db_lock

            updated_doc = await self.repository.find_one_and_update(
                filter=update_filter,
                update_data=new_data,
                return_document=True,
            )

            if not updated_doc:
                # Carrera entre la verificación y esta actualización:
                # otro usuario modificó el registro en el ínterim.
                logger.warning(
                    f"update_one_safely: carrera detectada en registro {id}; "
                    "el cerrojo cambió entre la verificación y la "
                    "actualización."
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Conflicto de edición: Los datos fueron modificados "
                        "por otro usuario. Por favor, recargue la página."
                    ),
                )

            return updated_doc
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en update_one_safely: {str(e)}")
            self._handle_error("Error durante el proceso de update_one_safely", e)

    # -------------------------------------------------
    async def delete_one(self, id: str) -> CtasCtesDocument:
        """Baja individual de una cuenta corriente.

        Args:
            id: Identificador ``_id`` del registro a eliminar.

        Returns:
            Documento eliminado.

        Raises:
            HTTPException: 404 si el registro no existe; 500 ante
                fallos inesperados.
        """
        try:
            mongo_id = ObjectId(id)
            document = await self.repository.delete_by_id(mongo_id)

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La Cuenta Corriente no existe o ya fue eliminada.",
                )
            return document
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_one: {str(e)}")
            self._handle_error("Error durante el proceso de delete_one", e)

    # --------------------------------------------------
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
