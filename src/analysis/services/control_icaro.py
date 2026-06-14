__all__ = ["ControlIcaroService", "ControlIcaroServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...utils import (
    BaseService,
)
from ..repositories import (
    ControlIcaroAnualRepositoryDependency,
    ControlIcaroComprobantesRepositoryDependency,
    ControlIcaroPA6RepositoryDependency,
)
from ..schemas import (
    ControlIcaroFullFilter,
    ControlIcaroLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlIcaroService:
    ctrl_anual: ControlIcaroAnualRepositoryDependency
    ctrl_comprobantes: ControlIcaroComprobantesRepositoryDependency
    ctrl_pa6: ControlIcaroPA6RepositoryDependency

    # -------------------------------------------------
    async def export(self, params: ControlIcaroLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ControlIcaroFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_ctrl_anual = await self.ctrl_anual.find_with_filter_params(
            params=search_params
        )
        df_ctrl_anual = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_anual]
        )
        data_ctrl_comprobantes = await self.ctrl_comprobantes.find_with_filter_params(
            params=search_params
        )
        df_ctrl_comprobantes = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_comprobantes]
        )
        data_ctrl_pa6 = await self.ctrl_pa6.find_with_filter_params(
            params=search_params
        )
        df_ctrl_pa6 = pd.DataFrame([d.model_dump(by_alias=True) for d in data_ctrl_pa6])

        # 3. Usar el método de la clase base
        return BaseService.export_to_excel(
            self,
            data_pairs=[
                (
                    df_ctrl_anual,
                    "control_ejecucion_anual_db",
                ),
                (
                    df_ctrl_comprobantes,
                    "control_comprobantes_db",
                ),
                (
                    df_ctrl_pa6,
                    "control_pa6_db",
                ),
            ],
            filename="Control Icaro vs SIIF.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1KKeeoop_v_Nf21s7eFp4sS6SmpxRZQ9DPa1A5wVqnZ0",
        )


ControlIcaroServiceDependency = Annotated[ControlIcaroService, Depends()]
