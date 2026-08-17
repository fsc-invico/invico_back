__all__ = [
    "ControlHaberesService",
    "ControlHaberesServiceDependency",
]

from dataclasses import dataclass
from datetime import date
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...icaro.schemas import RetencionesFullFilter
from ...icaro.services import RetencionesServiceDependency
from ...siif.schemas import Rci02FullFilter, Rcocc31FullFilter
from ...siif.services import (
    Rci02ServiceDependency,
    Rcocc31ServiceDependency,
)
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ControlAporteEmpresarioFilter,
    ControlAporteEmpresarioLiteFilter,
    ControlAporteEmpresarioReport,
)


@dataclass
# -------------------------------------------------
class ControlHaberesService:
    recursos_service: Rci02ServiceDependency
    retenciones_service: Rcocc31ServiceDependency
    icaro_service: RetencionesServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def get_siif_comprobantes_haberes_neto_rdeu(
        self,
        params: ControlAporteEmpresarioFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        recursos_params = Rci02FullFilter(
            query_filter="es_invico=true, es_verificado=true",
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        data = await self.recursos_service.get_all(params=recursos_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        df = df.rename(
            columns={
                "importe": "recurso",
            }
        )

        # 2. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "siif_recursos_cta_cte")

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(
        self, params: ControlAporteEmpresarioLiteFilter
    ) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ControlAporteEmpresarioFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_recursos = await self.get_recursos(params=params)
        data_retenciones_siif = await self.get_retenciones_from_siif(params=params)
        data_retenciones_icaro = await self.get_retenciones_from_icaro(params=params)
        data_control_siif = await self.generate_siif(params=params)
        data_control_icaro = await self.generate_icaro(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_recursos = pd.DataFrame(data_recursos)

        df_retenciones_siif = pd.DataFrame(data_retenciones_siif)

        df_retenciones_icaro = pd.DataFrame(data_retenciones_icaro)

        df_control_siif = pd.DataFrame(data_control_siif)

        df_control_icaro = pd.DataFrame(data_control_icaro)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_recursos, "recursos_siif_db"),
                (df_retenciones_siif, "retenciones_siif_db"),
                (df_retenciones_icaro, "retenciones_icaro_db"),
                (df_control_siif, "control_cruzado_siif_db"),
                (df_control_icaro, "control_cruzado_icaro_db"),
            ],
            filename="Control Aporte Empresario.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1bZnvl9YkHC-N1HbIbnFNrqU3Iq03PG81u7fdHe_v_pw",
        )


ControlHaberesServiceDependency = Annotated[ControlHaberesService, Depends()]
