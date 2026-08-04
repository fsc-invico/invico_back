__all__ = [
    "ReporteFormulacionService",
    "ReporteFormulacionServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.repositories import PlanillometroHistRepositoryDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ReporteFormulacionFilter,
    ReporteFormulacionLiteFilter,
    ReportePlanillometroFilter,
    ReportePlanillometroReport,
)
from .reporte_planillometro import ReportePlanillometroServiceDependency


@dataclass
# -------------------------------------------------
class ReporteFormulacionService:
    planillometro_service: ReportePlanillometroServiceDependency
    planillometro_hist_repo: PlanillometroHistRepositoryDependency

    # -------------------------------------------------
    async def generate_planillometro(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReportePlanillometroReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        planillometro_params = ReportePlanillometroFilter(
            ejercicio=params.ejercicio,
            limit=params.limit,
            desagregar_desc_subprog=True,
            desagregar_obras=False,
            desagregar_partida=False,
            desagregar_fuente=False,
            agregar_acum_2008=True,
            include_pa6=True,
        )

        return await self.planillometro_service.generate(params=planillometro_params)

    # -------------------------------------------------
    async def export(self, params: ReporteFormulacionLiteFilter) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ReporteFormulacionFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_planillometro = await self.generate_planillometro(params=params)

        # 3. Usar el método de la clase base
        df_planillometro = pd.DataFrame(data_planillometro)
        # df_planillometro = df_planillometro.rename(
        #     columns={
        #         "desc_programa": "desc_prog",
        #         "desc_proyecto": "desc_proy",
        #         "desc_actividad": "desc_act",
        #     }
        # )

        # sgv = await get_sgv_saldos_barrios_evolucion()
        # sgv["ejercicio"] = sgv["ejercicio"].astype(str)
        # sgv["cod_barrio"] = sgv["cod_barrio"].astype(int)
        # sgv = sgv.sort_values(by=["ejercicio", "cod_barrio"], ascending=[True, True])

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_planillometro, "planillometro_contabilidad"),
                # (sgv, "bd_recuperos"),
            ],
            filename="Reporte Formulación.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1hJyBOkA8sj5otGjYGVOzYViqSpmv_b4L8dXNju_GJ5Q",
        )


ReporteFormulacionServiceDependency = Annotated[ReporteFormulacionService, Depends()]
