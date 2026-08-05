__all__ = [
    "ReporteFormulacionService",
    "ReporteFormulacionServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.schemas import Rf602FullFilter, RfpP605bFullFilter, Ri102FullFilter
from ...siif.services import (
    Rf602ServiceDependency,
    RfpP605bServiceDependency,
    Ri102ServiceDependency,
)
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ReporteFormulacionCargaReport,
    ReporteFormulacionFilter,
    ReporteFormulacionGastosReport,
    ReporteFormulacionLiteFilter,
    ReporteFormulacionPlanillometroReport,
    ReporteFormulacionRecursosReport,
    ReportePlanillometroFilter,
)
from .reporte_planillometro import ReportePlanillometroServiceDependency


@dataclass
# -------------------------------------------------
class ReporteFormulacionService:
    planillometro_service: ReportePlanillometroServiceDependency
    recursos_service: Ri102ServiceDependency
    gastos_service: Rf602ServiceDependency
    formulacion_service: RfpP605bServiceDependency

    # -------------------------------------------------
    async def generate_planillometro(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionPlanillometroReport]:
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
    async def generate_recursos(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionRecursosReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        recursos_params = Ri102FullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        data = await self.recursos_service.get_all(params=recursos_params)

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

        # -------------------------------------------------

    async def generate_gastos(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionGastosReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = Rf602FullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        df = pd.DataFrame(
            await self.gastos_service.with_desc_estructuras(params=gastos_params)
        )
        df["fuente"] = pd.to_numeric(
            df["fuente"], errors="coerce"
        )  # Convertir a numérico
        df["programa"] = pd.to_numeric(df["programa"], errors="coerce")
        df = df.loc[
            :,
            [
                "ejercicio",
                "estructura",
                "partida",
                "fuente",
                "desc_programa",
                "desc_subprograma",
                "desc_proyecto",
                "desc_actividad",
                "programa",
                "grupo",
                "credito_original",
                "credito_vigente",
                "comprometido",
                "ordenado",
                "saldo",
            ],
        ]

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def generate_carga(
        self,
        params: ReporteFormulacionFilter,
    ) -> List[ReporteFormulacionCargaReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        recursos_params = RfpP605bFullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
        )

        data = await self.formulacion_service.get_all(params=recursos_params)

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
        data_planillometro = await self.generate_planillometro(params=params)
        data_recursos = await self.generate_recursos(params=params)
        data_gastos = await self.generate_gastos(params=params)
        params.ejercicio = str(
            int(params.ejercicio + 1)
        )  # Incrementamos el ejercicio para la formulación
        data_formulacion = await self.generate_carga(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_planillometro = pd.DataFrame(data_planillometro)
        df_planillometro["alta"] = pd.to_numeric(
            df_planillometro["alta"], errors="coerce"
        )  # Es necesario?

        df_recursos = pd.DataFrame(data_recursos)

        df_gastos = pd.DataFrame(data_gastos)
        df_formulacion = pd.DataFrame(data_formulacion)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_planillometro, "planillometro_contabilidad"),
                (df_recursos, "siif_recursos_cod"),
                (df_gastos, "siif_ejec_gastos"),
                (df_formulacion, "siif_carga_form_gastos"),
            ],
            filename="Reporte Formulación.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1hJyBOkA8sj5otGjYGVOzYViqSpmv_b4L8dXNju_GJ5Q",
        )


ReporteFormulacionServiceDependency = Annotated[ReporteFormulacionService, Depends()]
