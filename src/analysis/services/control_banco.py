__all__ = ["ControlBancoService", "ControlBancoServiceDependency"]

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
    ControlBancoCruzadoRepositoryDependency,
    ControlBancoSIIFRepositoryDependency,
    ControlBancoSSCCRepositoryDependency,
)
from ..schemas import (
    ControlBancoFullFilter,
    ControlBancoLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlBancoService:
    ctrl_cruzado: ControlBancoCruzadoRepositoryDependency
    ctrl_siif: ControlBancoSIIFRepositoryDependency
    ctrl_sscc: ControlBancoSSCCRepositoryDependency

    # -------------------------------------------------
    async def export(self, params: ControlBancoLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ControlBancoFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_ctrl_cruzado = await self.ctrl_cruzado.find_with_filter_params(
            params=search_params
        )
        df_ctrl_cruzado = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_cruzado]
        )
        data_ctrl_siif = await self.ctrl_siif.find_with_filter_params(
            params=search_params
        )
        df_ctrl_siif = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_siif]
        )
        data_ctrl_sscc = await self.ctrl_sscc.find_with_filter_params(
            params=search_params
        )
        df_ctrl_sscc = pd.DataFrame(
            [d.model_dump(by_alias=True) for d in data_ctrl_sscc]
        )

        # 3. Usar el método de la clase base
        return BaseService.export_to_excel(
            self,
            data_pairs=[
                (
                    df_ctrl_cruzado,
                    "siif_vs_sscc_db",
                ),
                (
                    df_ctrl_siif,
                    "siif_db",
                ),
                (
                    df_ctrl_sscc,
                    "sscc_db",
                ),
            ],
            filename="Control Banco SIIF vs SSCC.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1CRQjzIVzHKqsZE8_E1t8aRQDfWfZALhbe64WcxHiSM4",
        )


ControlBancoServiceDependency = Annotated[ControlBancoService, Depends()]
