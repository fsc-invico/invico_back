# utils/base_service.py
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from ..config import logger
from .safe_get import (
    sanitize_dataframe_for_json_with_datetime,  # Tu función de utilidad
)

# Tipos genéricos para que el Service sepa con qué Schema y Repository trabajar
R = TypeVar("R")  # Para el Schema del Reporte (ej. Rf602Report)
D = TypeVar("D")  # Para el Schema del Documento (ej. Rf602Document)
F = TypeVar("F")  # Para los Parámetros (ej. BaseFilterParams con paginación)
L = TypeVar("L")  # Parámetros Export (filtros, sin paginación)


# -------------------------------------------------
class BaseService(ABC, Generic[R, D, F, L]):
    # --------------------------------------------------
    def __init__(self, repository: Any, filter_schema: Type[F]):
        self.repository = repository
        self.filter_schema = filter_schema  # <--- Aquí guardamos la clase F

    @abstractmethod
    # --------------------------------------------------
    async def add_many(self, data: List[R], **kwargs) -> Any:
        """Método para inserción masiva"""
        pass

    # -------------------------------------------------
    async def get_all(self, params: F) -> List[D]:
        """
        Implementación genérica para recuperar registros con filtros.
        F: El esquema de filtros específico (ej. Rf602FullFilter)
        D: El esquema del documento específico (ej. Rf602Document)
        """
        try:
            # El repositorio ya debería estar tipado para manejar estos params
            return await self.repository.find_with_filter_params(params=params)
        except Exception as e:
            # Usamos un mensaje genérico o dinámico
            self._handle_error(f"Error retrieving data in {self.__class__.__name__}", e)

    # --------------------------------------------------
    async def delete_many(self, params: L) -> dict:
        """
        Implementación estándar para los 25 módulos.
        Se puede sobrescribir en el servicio específico si es necesario.
        """
        try:
            # 1. TRUCO MAESTRO: Convertimos params (ej. Rf602LiteFilter)
            # al tipo de filtro que el repositorio entiende (F, ej. Rf602FullFilter).
            # Esto inyecta el método 'get_full_filter' dinámicamente.
            full_filter_obj = self.filter_schema(
                **params.model_dump(exclude_none=True),
                limit=None,  # Nos aseguramos de que no haya límites en el borrado
            )

            # 2. Llamada al repositorio (que ya definiste)
            deleted_count = await self.repository.delete_with_filter_params(
                params=full_filter_obj
            )

            # 3. Retornar siguiendo estrictamente tu RouteReturnSchema
            return {
                "title": f"Proceso de eliminación en {self.__class__.__name__}",
                "deleted": deleted_count,
                "added": 0,
                "errors": [],
            }
        except ValueError as e:
            # Capturamos el error de seguridad (filtro vacío)
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            self._handle_error("Error en eliminación masiva", e)

    @abstractmethod
    # --------------------------------------------------
    async def export(self, params: L) -> StreamingResponse:
        """Este método debe ser implementado por el hijo"""
        pass

    # -------------------------------------------------
    def _handle_error(self, message: str, exception: Exception):
        """Método de utilidad interno para manejo de logs y errores"""
        logger.error(f"{message}: {exception}")
        raise HTTPException(
            status_code=500,
            detail=f"{message}: {str(exception)}",
        )

    # -------------------------------------------------
    def export_to_excel(
        self,
        data_pairs: List[Tuple[pd.DataFrame, str]],
        filename: str = "data.xlsx",
        spreadsheet_key: Optional[str] = None,
        upload_to_google_sheets: bool = False,
    ) -> StreamingResponse:
        """
        Método base para exportar uno o múltiples DataFrames a Excel/Google Sheets.
        """
        try:
            # 1. Preparar y Sanitizar
            sanitized_pairs = []
            for df, sheet_name in data_pairs:
                if not df.empty:
                    # Usamos tu utilidad de sanitización
                    df = sanitize_dataframe_for_json_with_datetime(df)
                    df = df.drop(columns=["_id"], errors="ignore")
                    sanitized_pairs.append((df, sheet_name))

            # 2. Lógica de Google Sheets (opcional)
            if upload_to_google_sheets and spreadsheet_key:
                from .google_sheets import (
                    GoogleSheets,
                )  # Import local para evitar ciclos

                gs = GoogleSheets()
                for df, sheet_name in sanitized_pairs:
                    gs.to_google_sheets(
                        df=df,
                        spreadsheet_key=spreadsheet_key,
                        wks_name=sheet_name,
                    )

            # 3. Generar Buffer Excel
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                for df, sheet_name in sanitized_pairs:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
            buffer.seek(0)

            # 4. Retornar Respuesta
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            return StreamingResponse(
                buffer,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers=headers,
            )

        except Exception as e:
            self._handle_error("Error al exportar datos a Excel", e)
