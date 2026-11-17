__all__ = [
    "ControlAporteEmpresarioService",
    "ControlAporteEmpresarioServiceDependency",
]

import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.concurrency import run_in_threadpool

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
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories import ControlAporteEmpresarioRepositoryDependency
from ..schemas import (
    ControlAporteEmpresarioDocument,
    ControlAporteEmpresarioFilter,
    ControlAporteEmpresarioLiteFilter,
    ControlAporteEmpresarioReport,
)

SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO: str = (
    "1bZnvl9YkHC-N1HbIbnFNrqU3Iq03PG81u7fdHe_v_pw"
)

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


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
    ) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube las hojas ``recursos_siif_db``, ``retenciones_siif_db``,
        ``retenciones_icaro_db``, ``control_cruzado_siif_db`` y
        ``control_cruzado_icaro_db``. NO se genera el archivo Excel
        (patrón ``control_viaticos``): el trabajo pesado corre como tarea
        de fondo para no bloquear el event loop ni agotar el timeout de
        Koyeb.

        Se encola con ``asyncio.create_task`` (y no con ``BackgroundTasks``)
        para ser compatible con la ruta ``/export`` del
        ``GenericRouterFactory``, que no inyecta ``BackgroundTasks``.
        """
        asyncio.create_task(self._export_to_google_sheets(params))
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "recursos_siif_db, retenciones_siif_db, retenciones_icaro_db, "
                "control_cruzado_siif_db y control_cruzado_icaro_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlAporteEmpresarioLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        NO genera el archivo Excel (a diferencia del export binario
        anterior): solo queries + upload, corriendo fuera del request.
        Procesa de a una hoja para mantener el pico de memoria acotado
        (Koyeb dispone de poca RAM en su capa gratuita).

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        filter_params = ControlAporteEmpresarioFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Fuentes crudas + cruce ICARO
            data_recursos = await self.get_recursos(params=filter_params)
            data_retenciones_siif = await self.get_retenciones_from_siif(
                params=filter_params
            )
            data_retenciones_icaro = await self.get_retenciones_from_icaro(
                params=filter_params
            )
            data_control_icaro = await self.generate_icaro(
                params=filter_params
            )

            # El cruce SIIF (la tabla que ve el usuario en la página) se
            # exporta desde el snapshot persistido en Mongo; si todavía no
            # existe, se calcula on-demand para no dejar la hoja vacía.
            snapshot = await self.repository.find_with_filter_params(
                params=filter_params
            )
            data_control_siif = (
                [doc.model_dump(by_alias=True) for doc in snapshot]
                if snapshot
                else await self.generate_siif(params=filter_params)
            )

            # 2. DataFrames + upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[pd.DataFrame, str]] = [
                (pd.DataFrame(data_recursos), "recursos_siif_db"),
                (pd.DataFrame(data_retenciones_siif), "retenciones_siif_db"),
                (pd.DataFrame(data_retenciones_icaro), "retenciones_icaro_db"),
                (pd.DataFrame(data_control_siif), "control_cruzado_siif_db"),
                (pd.DataFrame(data_control_icaro), "control_cruzado_icaro_db"),
            ]
            for df, sheet_name in sheets:
                try:
                    await run_in_threadpool(
                        self._build_df_and_upload, df, sheet_name
                    )
                    logger.info(
                        f"Control Aporte Empresario: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Aporte Empresario: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info(
            "Control Aporte Empresario: exportación a Google Sheets finalizada"
        )

    # -------------------------------------------------
    @staticmethod
    def _build_df_and_upload(df: pd.DataFrame, sheet_name: str) -> None:
        """Descarta los id internos y sube la hoja (bloqueante → threadpool).

        NO genera el archivo Excel: solo sube la hoja a Google Sheets.

        Sanitiza explícitamente (defensa en profundidad) para que ninguna
        celda viaje como ``nan``: gspread serializa con
        ``json.dumps(allow_nan=False)`` y una sola celda NaN aborta la
        subida completa con 'Out of range float values are not JSON
        compliant: nan' (hoja vacía en Google Sheets).
        """
        df = df.drop(columns=["id", "_id"], errors="ignore")
        df = sanitize_dataframe_for_json_with_datetime(df)
        upload_multiple_dataframes_to_google_sheets(
            [(df, sheet_name)],
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_APORTE_EMPRESARIO,
        )


ControlAporteEmpresarioServiceDependency = Annotated[
    ControlAporteEmpresarioService, Depends()
]
