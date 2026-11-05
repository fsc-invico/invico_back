__all__ = [
    "ControlAporteEmpresarioService",
    "ControlAporteEmpresarioServiceDependency",
]

from dataclasses import dataclass
from datetime import date
from typing import Annotated, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...config import logger
from ...icaro.schemas import RetencionesFullFilter
from ...icaro.services import RetencionesServiceDependency
from ...siif.schemas import Rci02FullFilter, Rcocc31FullFilter
from ...siif.services import (
    Rci02ServiceDependency,
    Rcocc31ServiceDependency,
)
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ControlAporteEmpresarioRepositoryDependency
from ..schemas import (
    ControlAporteEmpresarioDocument,
    ControlAporteEmpresarioFilter,
    ControlAporteEmpresarioLiteFilter,
    ControlAporteEmpresarioReport,
)


@dataclass
# -------------------------------------------------
class ControlAporteEmpresarioService(
    BaseService[
        ControlAporteEmpresarioReport,
        ControlAporteEmpresarioDocument,
        ControlAporteEmpresarioFilter,
        ControlAporteEmpresarioLiteFilter,
    ]
):
    repository: ControlAporteEmpresarioRepositoryDependency
    recursos_service: Rci02ServiceDependency
    retenciones_service: Rcocc31ServiceDependency
    icaro_service: RetencionesServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlAporteEmpresarioFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[ControlAporteEmpresarioReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce (snapshot) con borrado idempotente por ejercicio.

        Es la contraparte del ``GET /generateIcaro``: el frontend计算 el
        reporte on-demand y luego llama aquí para congelarlo en la
        colección ``control_aporte_empresario`` (patrón generate -> POST
        de reporte_planillometro / control_recursos).
        """
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlAporteEmpresarioReport,
                field_id=[
                    "ejercicio",
                    "mes",
                    "cta_cte",
                ],  # Clave de la fila del cruce
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Aporte Empresario",
                label="Control Aporte Empresario",
                logger=logger,
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

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
    async def get_retenciones_from_siif(
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
    async def get_retenciones_from_icaro(
        self,
        params: ControlAporteEmpresarioFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        retenciones_params = RetencionesFullFilter(
            query_filter="codigo=str:337",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.icaro_service.get_retenciones_with_carga(
            params=retenciones_params
        )
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Eliminamos PA6 o REGs según correponda
        delete_tipo = "REG" if params.ejercicio == date.today().year else "PA6"
        df = df.loc[df["tipo"] != delete_tipo]

        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Renombramos campos
        df = df.rename(columns={"importe": "retencion_pagada"})

        # 4. Unificación de Cuenta Corriente
        df = await self.cta_cte_service.cta_cte_unifier(df, "icaro_cta_cte")

        # 7. Reemplazo explicito de NaNs por None (null en JSON)
        # Esto previene el error 'Out of range float values are not JSON compliant: nan'
        records = df.replace({np.nan: None}).to_dict(orient="records")

        return records

    # -------------------------------------------------
    async def generate_siif(
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

        data = await self.get_retenciones_from_siif(params=params)
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

        df = df.loc[
            :,
            ["ejercicio", "mes", "cta_cte", "recurso", "retencion"],
        ]

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def generate_icaro(
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

        data = await self.get_retenciones_from_icaro(params=params)
        icaro_retenciones = pd.DataFrame(data)
        # Validación por si el DataFrame de retenciones llega vacío
        if not icaro_retenciones.empty and all(
            col in icaro_retenciones.columns for col in groupby_cols
        ):
            icaro_retenciones = icaro_retenciones.loc[
                :, ["ejercicio", "mes", "cta_cte", "retencion_pagada"]
            ]
            icaro_retenciones = (
                icaro_retenciones.groupby(groupby_cols)
                .sum(numeric_only=True)
                .reset_index()
                .fillna(0)
            )

            icaro_retenciones = icaro_retenciones.rename(
                columns={"retencion_pagada": "retencion"}
            )
            if "retencion" in icaro_retenciones.columns:
                icaro_retenciones["retencion"] = icaro_retenciones["retencion"] * (-1)

        df = siif_recursos.merge(icaro_retenciones, how="outer", on=groupby_cols)
        df = df.fillna(0)

        df = df.loc[
            :,
            ["ejercicio", "mes", "cta_cte", "recurso", "retencion"],
        ]

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

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
        data_control_icaro = await self.generate_icaro(params=params)

        # El cruce ICARO (la tabla que ve el usuario en la página) se
        # exporta desde el snapshot persistido en Mongo; si todavía no
        # existe, se calcula on-demand para no dejar la hoja vacía.
        snapshot = await self.repository.find_with_filter_params(params=params)
        data_control_siif = (
            [doc.model_dump(by_alias=True) for doc in snapshot]
            if snapshot
            else await self.generate_siif(params=params)
        )

        # 3. Transformamos los datos a DataFrames de Pandas
        df_recursos = pd.DataFrame(data_recursos)

        df_retenciones_siif = pd.DataFrame(data_retenciones_siif)

        df_retenciones_icaro = pd.DataFrame(data_retenciones_icaro)

        df_control_siif = pd.DataFrame(data_control_siif)

        df_control_icaro = pd.DataFrame(data_control_icaro)

        return self.export_to_excel(
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


ControlAporteEmpresarioServiceDependency = Annotated[
    ControlAporteEmpresarioService, Depends()
]
