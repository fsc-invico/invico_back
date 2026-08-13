__all__ = [
    "ControlAporteEmpresarioService",
    "ControlAporteEmpresarioServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

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
class ControlAporteEmpresarioService:
    recursos_service: Rci02ServiceDependency
    retenciones_service: Rcocc31ServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def get_recursos(
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
    async def get_retenciones(
        self,
        params: ControlAporteEmpresarioFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        retenciones_params = Rcocc31FullFilter(
            query_filter="tipo_comprobante!=APE",
            ejercicio=str(params.ejercicio),
            cta_contable="2122-1-2, 1112-2-6",
            limit=None,
        )

        data = await self.retenciones_service.get_all(params=retenciones_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        if df.empty or "cta_contable" not in df.columns:
            return []

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Filtrado e indexación de SIIF Banco (1112-2-6)
        siif_banco = df.loc[df["cta_contable"] == "1112-2-6"]
        siif_banco = siif_banco.loc[
            :,
            ["ejercicio", "nro_entrada", "auxiliar_1"],
        ]
        siif_banco = siif_banco.rename(columns={"auxiliar_1": "cta_cte"})

        # 3. Filtrado de SIIF 337 (2122-1-2)
        cols_337 = [
            "ejercicio",
            "mes",
            "fecha",
            "nro_entrada",
            "tipo_comprobante",
            "debitos",
            "creditos",
        ]
        # Filtrar solo columnas existentes por seguridad
        cols_337_presentes = [c for c in cols_337 if c in df.columns]

        siif_337 = df.loc[
            (df["cta_contable"] == "2122-1-2") & (df["auxiliar_1"] == "337"),
            cols_337_presentes,
        ].rename(
            columns={
                "debitos": "retencion_pagada",
                "creditos": "retencion_practicada",
            }
        )

        if siif_337.empty:
            return []

        merged_df = siif_337.merge(
            siif_banco, how="left", on=["ejercicio", "nro_entrada"]
        )

        # 5. Unificación de Cuenta Corriente
        merged_df = await self.cta_cte_service.cta_cte_unifier(
            merged_df, "siif_contabilidad_cta_cte"
        )

        # 6. Sanitización final
        merged_df = sanitize_dataframe_for_json_with_datetime(merged_df)

        if params.limit is not None and params.limit > 0:
            merged_df = merged_df.head(params.limit)

        # 7. Reemplazo explicito de NaNs por None (null en JSON)
        # Esto previene el error 'Out of range float values are not JSON compliant: nan'
        records = merged_df.replace({np.nan: None}).to_dict(orient="records")

        return records

    # -------------------------------------------------
    async def generate(
        self,
        params: ControlAporteEmpresarioFilter,
    ) -> List[ControlAporteEmpresarioReport]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "mes", "cta_cte"]

        recursos_params = Rci02FullFilter(
            query_filter="es_invico=true, es_verificado=true",
            ejercicio=str(params.ejercicio),
            limit=None,
        )
        data = await self.recursos_service.summarize(
            params=recursos_params, groub_by=groupby_cols
        )
        siif_recursos = pd.DataFrame(data)
        siif_recursos = siif_recursos.rename(
            columns={
                "importe": "recurso",
            }
        )
        siif_recursos = await self.cta_cte_service.cta_cte_unifier(
            siif_recursos, "siif_recursos_cta_cte"
        )

        data = await self.get_retenciones(params=params)
        siif_retenciones = pd.DataFrame(data)
        # Validación por si el DataFrame de retenciones llega vacío
        if not siif_retenciones.empty and all(
            col in siif_retenciones.columns for col in groupby_cols
        ):
            siif_retenciones = (
                siif_retenciones.groupby(groupby_cols)
                .sum(numeric_only=True)
                .reset_index()
                .fillna(0)
            )
            if "retencion_practicada" in siif_retenciones.columns:
                siif_retenciones.drop(columns=["retencion_practicada"], inplace=True)

            siif_retenciones = siif_retenciones.rename(
                columns={"retencion_pagada": "retencion"}
            )
            if "retencion" in siif_retenciones.columns:
                siif_retenciones["retencion"] = siif_retenciones["retencion"] * (-1)

        df = siif_recursos.merge(siif_retenciones, how="outer", on=groupby_cols)
        df = df.fillna(0)

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
        data_retenciones = await self.get_retenciones(params=params)
        data_control = await self.generate(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_recursos = pd.DataFrame(data_recursos)

        df_retenciones = pd.DataFrame(data_retenciones)

        df_control = pd.DataFrame(data_control)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_recursos, "recursos_db"),
                (df_retenciones, "retenciones_db"),
                (df_control, "recursos_vs_retenciones_db"),
            ],
            filename="Control Aporte Empresario.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1bZnvl9YkHC-N1HbIbnFNrqU3Iq03PG81u7fdHe_v_pw",
        )


ControlAporteEmpresarioServiceDependency = Annotated[
    ControlAporteEmpresarioService, Depends()
]
