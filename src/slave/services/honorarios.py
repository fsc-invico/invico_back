__all__ = ["HonorariosService", "HonorariosServiceDependency"]


from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, List

import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import HonorariosRepositoryDependency
from ..schemas import (
    HonorariosDocument,
    HonorariosFullFilter,
    HonorariosLiteFilter,
    HonorariosReport,
    HonorariosUpdate,
)


@dataclass
# -------------------------------------------------
class HonorariosService(
    BaseService[
        HonorariosReport, HonorariosDocument, HonorariosFullFilter, HonorariosLiteFilter
    ]
):
    repository: HonorariosRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=HonorariosFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[HonorariosReport], delete_filter: dict = None
    ) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=HonorariosReport,
                field_id=[
                    "mes",
                    "nro_comprobante",
                    "nombre_completo",
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
            if delete_filter is None:
                delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Honorarios SLAVE",
                label=f"Honorarios Slave del Ejercicio {ejercicio_detectado}",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: HonorariosLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = HonorariosFullFilter(
            query_filter=params.query_filter,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SLAVE_HONORARIOS")], filename="slave_honorarios.xlsx"
        )

    # -------------------------------------------------
    async def get_tipos_comprobantes(self) -> List[str]:
        """Devuelve los valores únicos del campo 'tipo' en slave_honorarios.

        Usa el comando `distinct` de MongoDB para obtener los tipos de
        comprobante sin traer toda la colección a la memoria.
        """
        try:
            # collection es el AsyncIOMotorCollection expuesto por BaseRepository.
            valores = await self.repository.collection.distinct("tipo")

            # Filtramos valores vacíos/nulos y forzamos la unicidad (por si el
            # backend no la garantiza), luego ordenamos alfabéticamente para
            # devolver una lista estable y predecible al frontend.
            return sorted({valor for valor in valores if valor})
        except Exception as e:
            self._handle_error("Error obteniendo los tipos de comprobantes", e)

    # -------------------------------------------------
    async def delete_many_by_nro_comprobante(self, nro_comprobante: str) -> dict:
        try:
            count = await self.repository.delete_by_fields(
                {"nro_comprobante": nro_comprobante}
            )

            return {
                "status": "success",
                "deleted_count": count,
                "message": f"Se eliminaron {count} honorarios asociados.",
            }

        except Exception as e:
            logger.error(f"Error en delete_many_by_nro_comprobante: {str(e)}")
            self._handle_error("Error eliminando honorarios", e)

    # -------------------------------------------------
    async def update_many_by_nro_comprobante(
        self, nro_comprobante: str, update_data: HonorariosUpdate
    ) -> dict:
        try:
            # Solo enviamos al $set los campos que el cliente realmente envió,
            # así los campos omitidos no pisan los valores existentes en Mongo.
            payload = update_data.model_dump(exclude_unset=True)

            # nro_comprobante: la path es el valor ACTUAL (filtro) y el del
            # payload, si viene, es el NUEVO valor con el que se renombrarán
            # todos los documentos. Un null explícito se descarta para no
            # romper la identidad de los documentos.
            if payload.get("nro_comprobante") is None:
                payload.pop("nro_comprobante", None)

            # Regla de negocio: los comprobantes que no son Honorarios van al 399.
            if update_data.tipo != "Honorarios":
                payload["partida"] = "399"
            # Si es Honorarios y no vino partida (o vino null), no pisamos la
            # guardada: un null rompería la validación de HonorariosReport al leer.
            elif payload.get("partida") is None:
                payload.pop("partida", None)

            # El timestamp lo asigna siempre el servidor, nunca el cliente.
            payload["updated_at"] = datetime.now(timezone.utc)

            # Detección de conflicto: si se pide renombrar a un nro_comprobante
            # que ya corresponde a OTROS documentos (distintos de los del
            # filtro), el update_many los fusionaría en un mismo comprobante.
            nuevo_nro = payload.get("nro_comprobante")
            if nuevo_nro is not None and nuevo_nro != nro_comprobante:
                existentes = await self.repository.count_by_fields(
                    {"nro_comprobante": nuevo_nro}
                )
                if existentes > 0:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Ya existen {existentes} registro(s) con el "
                            f"nro_comprobante '{nuevo_nro}'. Use otro número."
                        ),
                    )

            # update_many: el filtro usa el nro_comprobante VIEJO (path) y el
            # $set aplica el mismo payload (incluido el nuevo nro_comprobante,
            # si vino) a todos los documentos coincidentes.
            modificados = await self.repository.update_many(
                {"nro_comprobante": nro_comprobante}, payload
            )
            if modificados > 0:
                logger.info(f"Se actualizaron {modificados} registros.")

            return {"status": "updated", "modified_count": modificados}
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            self._handle_error(
                f"Error al modificar el nro_comprobante {nro_comprobante}", e
            )

    # -------------------------------------------------
    async def add_many_by_nro_comprobante(
        self, data: List[HonorariosReport], delete_filter: dict = None
    ) -> RouteReturnSchema:
        try:
            # Regla de negocio: si el tipo no es "Honorarios", la partida de
            # todos los documentos debe guardarse como "399". Se aplica sobre
            # el payload crudo (antes de validar) para poder completar la
            # partida aunque no venga en el request. Normalizamos a dict porque
            # la ruta genérica del factory envía dicts y
            # add_many/{nro_comprobante} envía modelos Pydantic.
            records = [
                item if isinstance(item, dict) else item.model_dump()
                for item in data
            ]
            for record in records:
                if record.get("tipo") != "Honorarios":
                    record["partida"] = "399"

            # Detección de conflicto (misma filosofía que en
            # update_many_by_nro_comprobante): no se permite agregar un
            # comprobante cuyo nro_comprobante ya exista en la BD. Verificamos
            # solo el nro del delete_filter (path), que coincide con el de
            # todos los registros del payload.
            nro_path = (delete_filter or {}).get("nro_comprobante")
            if nro_path:
                existentes = await self.repository.count_by_fields(
                    {"nro_comprobante": nro_path}
                )
                if existentes > 0:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Ya existen {existentes} registro(s) con el "
                            f"nro_comprobante '{nro_path}'. Use otro número o "
                            f"actualice el comprobante existente."
                        ),
                    )

            # add_many valida, borra los previos (delete_filter) e inserta.
            return await self.add_many(data=records, delete_filter=delete_filter)
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            self._handle_error(
                "Error durante el proceso de add_many_by_nro_comprobante", e
            )


HonorariosServiceDependency = Annotated[HonorariosService, Depends()]
