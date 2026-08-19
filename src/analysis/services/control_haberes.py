__all__ = [
    "ControlHaberesService",
    "ControlHaberesServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.schemas import GtoRpa03gFullFilter
from ...siif.services import (
    GtoRpa03gServiceDependency,
)
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ControlHaberesFilter,
    ControlHaberesLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlHaberesService:
    gastos_service: GtoRpa03gServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def get_siif_comprobantes_haberes_neto_rdeu(
        self,
        params: ControlHaberesFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )
        gastos_params.set_extra_filter({"partida": {"$nin": ["150", "151"]}})

        data = await self.gastos_service.get_joined_with_rcg01_uejp(
            params=gastos_params
        )
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 3. Filtramos la cuenta 130830-04
        df = df.loc[df["cta_cte"] == "130832004"]

        # 4. Traemos la deuda flotante filtrada

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "siif_gastos_cta_cte")

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlHaberesLiteFilter) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ControlHaberesFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_haberes = await self.get_siif_comprobantes_haberes_neto_rdeu(params=params)
        # data_retenciones_siif = await self.get_retenciones_from_siif(params=params)
        # data_retenciones_icaro = await self.get_retenciones_from_icaro(params=params)
        # data_control_siif = await self.generate_siif(params=params)
        # data_control_icaro = await self.generate_icaro(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_haberes = pd.DataFrame(data_haberes)

        # df_retenciones_siif = pd.DataFrame(data_retenciones_siif)

        # df_retenciones_icaro = pd.DataFrame(data_retenciones_icaro)

        # df_control_siif = pd.DataFrame(data_control_siif)

        # df_control_icaro = pd.DataFrame(data_control_icaro)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_haberes, "siif_comprobantes_haberes_db"),
                # (df_retenciones_siif, "retenciones_siif_db"),
                # (df_retenciones_icaro, "retenciones_icaro_db"),
                # (df_control_siif, "control_cruzado_siif_db"),
                # (df_control_icaro, "control_cruzado_icaro_db"),
            ],
            filename="Control Haberes.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1A9ypUkwm4kfLqUAwr6-55crcFElisOO9fOdI6iflMAc",
        )


ControlHaberesServiceDependency = Annotated[ControlHaberesService, Depends()]
