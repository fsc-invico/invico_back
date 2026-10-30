__all__ = ["ControlBancoService", "ControlBancoServiceDependency"]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any

import pandas as pd
from fastapi import BackgroundTasks, Depends
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...utils import (
    upload_multiple_dataframes_to_google_sheets,
)
from ..repositories import (
    ControlBancoCruzadoRepositoryDependency,
    ControlBancoSIIFRepositoryDependency,
    ControlBancoSSCCRepositoryDependency,
)
from ..schemas import (
    ControlBancoFullFilter,
    ControlBancoLiteFilter,
)

SPREADSHEET_KEY_CONTROL_BANCO: str = "1CRQjzIVzHKqsZE8_E1t8aRQDfWfZALhbe64WcxHiSM4"

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlBancoService:
    ctrl_cruzado: ControlBancoCruzadoRepositoryDependency
    ctrl_siif: ControlBancoSIIFRepositoryDependency
    ctrl_sscc: ControlBancoSSCCRepositoryDependency

    # -------------------------------------------------
    async def export(
        self,
        params: ControlBancoLiteFilter,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        El trabajo pesado (queries, sanitizado y upload) corre como tarea de
        fondo para no bloquear el event loop ni agotar el timeout de Koyeb.
        """
        background_tasks.add_task(self._export_to_google_sheets, params)
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "siif_vs_sscc_db, siif_db y sscc_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_BANCO,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(self, params: ControlBancoLiteFilter) -> None:
        """Tarea de fondo: sube cada colección a su hoja, una por vez.

        Procesa de a una colección para mantener el pico de memoria acotado
        (Koyeb dispone de poca RAM en su capa gratuita).
        """
        search_params = ControlBancoFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        sources: list[tuple[Any, str]] = [
            (self.ctrl_cruzado, "siif_vs_sscc_db"),
            (self.ctrl_siif, "siif_db"),
            (self.ctrl_sscc, "sscc_db"),
        ]
        async with _export_lock:
            for repository, sheet_name in sources:
                try:
                    documents = await repository.find_with_filter_params(
                        params=search_params
                    )
                    # DataFrame + sanitizado + upload corren fuera del event loop
                    await run_in_threadpool(
                        self._build_df_and_upload, documents, sheet_name
                    )
                    del documents  # Liberar memoria antes de la siguiente hoja
                    logger.info(
                        f"Control Banco: hoja '{sheet_name}' actualizada en Google Sheets"
                    )
                except Exception as e:
                    # En background no hay respuesta HTTP que retornar: logueamos
                    # para que el error sea visible en los logs de Koyeb.
                    logger.error(
                        f"Control Banco: error al subir la hoja '{sheet_name}': {e}"
                    )
        logger.info("Control Banco: exportación a Google Sheets finalizada")

    # -------------------------------------------------
    @staticmethod
    def _build_df_and_upload(documents: list[Any], sheet_name: str) -> None:
        """Construye el DataFrame y sube la hoja (bloqueante → threadpool)."""
        df = pd.DataFrame(
            [document.model_dump(by_alias=True) for document in documents]
        )
        upload_multiple_dataframes_to_google_sheets(
            [(df, sheet_name)],
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_BANCO,
        )


ControlBancoServiceDependency = Annotated[ControlBancoService, Depends()]
