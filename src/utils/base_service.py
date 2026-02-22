# utils/base_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Generic, List, Optional, Tuple, TypeVar

import pandas as pd
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from ..config import logger
from .safe_get import (
    sanitize_dataframe_for_json_with_datetime,  # Tu función de utilidad
)

# Tipos genéricos para que el Service sepa con qué Schema y Repository trabajar
T = TypeVar("T")  # Para el Schema del Documento (ej. Rf602Document)
F = TypeVar("F")  # Para los Parámetros (ej. BaseFilterParams con paginación)
E = TypeVar("E")  # Parámetros Export (filtros, sin paginación)


@dataclass
# -------------------------------------------------
class BaseService(ABC, Generic[T, F, E]):
    repository: Any  # Se sobrescribirá en el hijo con el tipo específico

    @abstractmethod
    # -------------------------------------------------
    async def get_all(self, params: F) -> List[T]:
        """Método obligatorio a implementar"""
        pass

    @abstractmethod
    # --------------------------------------------------
    async def add_many(self):
        """Este método debe ser implementado por el hijo"""
        pass

    @abstractmethod
    # --------------------------------------------------
    async def delete_many(self):
        """Este método debe ser implementado por el hijo"""
        pass

    @abstractmethod
    # --------------------------------------------------
    async def export(self, params: E) -> StreamingResponse:
        """Este método debe ser implementado por el hijo"""
        pass

    # -------------------------------------------------
    def _handle_error(self, message: str, exception: Exception):
        """Método de utilidad interno para manejo de logs y errores"""
        logger.error(f"{message}: {exception}")
        raise HTTPException(
            status_code=500,
            detail=message,
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
