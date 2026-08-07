__all__ = [
    "ControlAporteEmpresarioService",
    "ControlAporteEmpresarioServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.schemas import Rci02FullFilter, Rcocc31FullFilter
from ...siif.services import (
    Rci02ServiceDependency,
    Rcocc31ServiceDependency,
)
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ReporteFormulacionFilter,
    ReporteFormulacionGastosReport,
    ReporteFormulacionLiteFilter,
    ReporteFormulacionRecursosReport,
)


@dataclass
# -------------------------------------------------
class ControlAporteEmpresarioService:
    recursos_service: Rci02ServiceDependency
    retenciones_service: Rcocc31ServiceDependency

    # -------------------------------------------------
    async def get_recursos(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionRecursosReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        recursos_params = Rci02FullFilter(
            query_filter="es_invico=true, es_verificado=true",
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        data = await self.recursos_service.get_all(params=recursos_params)

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        df = df.rename(
            columns={
                "importe": "recurso",
            }
        )

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

        # -------------------------------------------------

    async def get_retenciones(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionGastosReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        retenciones_params = Rcocc31FullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        data = await self.retenciones_service.get_all(params=retenciones_params)

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ReporteFormulacionLiteFilter) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ReporteFormulacionFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_recursos = await self.get_recursos(params=params)
        data_retenciones = await self.get_retenciones(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_recursos = pd.DataFrame(data_recursos)

        df_retenciones = pd.DataFrame(data_retenciones)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_recursos, "recursos_db"),
                (df_retenciones, "retenciones_db"),
            ],
            filename="Control Aporte Empresario.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1bZnvl9YkHC-N1HbIbnFNrqU3Iq03PG81u7fdHe_v_pw",
        )


ControlAporteEmpresarioServiceDependency = Annotated[
    ControlAporteEmpresarioService, Depends()
]
