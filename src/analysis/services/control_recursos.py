__all__ = ["ControlRecursosService", "ControlRecursosServiceDependency"]

# import os
import asyncio
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

# from pydantic import ValidationError
from ...config import logger
from ...sscc.schemas import BancoINVICOFullFilter
from ...sscc.services import BancoINVICOServiceDependency
from ...siif.schemas import Rci02FullFilter
from ...siif.services import Rci02ServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories import ControlRecursosRepositoryDependency
from ..schemas import (
    ControlRecursosDocument,
    ControlRecursosFullFilter,
    ControlRecursosGenerateFilter,
    ControlRecursosLiteFilter,
    ControlRecursosReport,
)

SPREADSHEET_KEY_CONTROL_RECURSOS: str = (
    "1u_I5wN3w_rGX6rWIsItXkmwfIEuSox6ZsmKYbMZ2iUY"
)

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlRecursosService(
    BaseService[
        ControlRecursosReport,
        ControlRecursosDocument,
        ControlRecursosFullFilter,
        ControlRecursosLiteFilter,
    ]
):
    repository: ControlRecursosRepositoryDependency
    siif_service: Rci02ServiceDependency
    banco_service: BancoINVICOServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlRecursosFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ControlRecursosReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlRecursosReport,
                field_id=[
                    "mes",
                    "cta_cte",
                    "grupo",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Recursos",
                label="Control Recursos",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self,
        params: ControlRecursosGenerateFilter,
    ) -> List[ControlRecursosReport]:
        """Cruce SIIF rci02 vs SSCC Banco INVICO calculado en el backend.

        Replica el cómputo que el frontend ejecutaba localmente en
        ``compute_control_recursos``: filtro de comprobantes verificados,
        mapeo de grupo (FONAVI / RECUPEROS / OTROS), suma de importes por
        ``[ejercicio, mes, cta_cte, grupo]`` y ``merge outer`` entre SIIF
        y depósitos del Banco INVICO.

        Lee las colecciones crudas directamente de MongoDB sin
        descargarlas al cliente. El resultado es una vista on-demand: el
        snapshot en la colección ``control_recursos`` lo congela el
        frontend con el ``POST`` posterior (patrón generate -> POST de
        reporte_planillometro).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Lista de filas del cruce validadas como
            ``ControlRecursosReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        group_by = ["ejercicio", "mes", "cta_cte", "grupo"]
        siif = await self._generate_siif_recursos(params.ejercicio, group_by)
        sscc = await self._generate_depositos_banco(params.ejercicio, group_by)

        df = pd.merge(siif, sscc, how="outer")
        df = df.fillna(0)

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def _generate_siif_recursos(
        self, ejercicio: int, group_by: List[str]
    ) -> pd.DataFrame:
        """Suma de recursos SIIF (rci02) verificados y no remanentes.

        Args:
            ejercicio: Ejercicio fiscal a consultar.
            group_by: Campos de agrupación del cruce.

        Returns:
            DataFrame ``[group_by..., recursos_siif]`` agregado por clave.
        """
        rci02_params = Rci02FullFilter(ejercicio=str(ejercicio), limit=None)
        data = await self.siif_service.get_all(params=rci02_params)
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        if df.empty:
            return pd.DataFrame(columns=group_by + ["recursos_siif"])

        # Mismos filtros que aplicaba el front:
        # solo verificados, sin remanentes y sin comprobantes de INVICO.
        df = df.loc[df["es_verificado"]]
        df = df.loc[~df["es_remanente"]]
        df = df.loc[~df["es_invico"]]

        if df.empty:
            return pd.DataFrame(columns=group_by + ["recursos_siif"])

        # Unificación de glosas MACRO (mapeo histórico del front)
        df.loc[df["glosa"].str.contains("MACRO", na=False), "cta_cte"] = "Macro"
        df["grupo"] = np.where(
            df["cta_cte"] == "10270",
            "FONAVI",
            np.where(
                df["cta_cte"].isin(["130832-12", "334", "Macro", "Patagonia"]),
                "RECUPEROS",
                "OTROS",
            ),
        )

        df = df.groupby(group_by)["importe"].sum()
        df = df.reset_index()
        return df.rename(columns={"importe": "recursos_siif"})

    # -------------------------------------------------
    async def _generate_depositos_banco(
        self, ejercicio: int, group_by: List[str]
    ) -> pd.DataFrame:
        """Depósitos del Banco INVICO excluyendo conceptos no cruzables.

        Filtra ``movimiento == DEPOSITO`` y descarta transferencias
        internas (034, 004), plazo fijo (214, 215), otros conceptos
        (003, 055, 005, 013) y certificados negativos (18).

        Args:
            ejercicio: Ejercicio fiscal a consultar.
            group_by: Campos de agrupación del cruce.

        Returns:
            DataFrame ``[group_by..., depositos_banco]`` agregado por clave.
        """
        banco_params = BancoINVICOFullFilter(ejercicio=str(ejercicio), limit=None)
        data = await self.banco_service.get_all(params=banco_params)
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        if df.empty:
            return pd.DataFrame(columns=group_by + ["depositos_banco"])

        dep_transf_int = ["034", "004"]
        dep_pf = ["214", "215"]
        dep_otros = ["003", "055", "005", "013"]
        dep_cert_neg = ["18"]

        df = df.loc[df["movimiento"] == "DEPOSITO"]
        df = df.loc[
            ~df["cod_imputacion"].isin(
                dep_transf_int + dep_pf + dep_otros + dep_cert_neg
            )
        ]

        if df.empty:
            return pd.DataFrame(columns=group_by + ["depositos_banco"])

        df["grupo"] = np.where(
            df["cta_cte"] == "10270",
            "FONAVI",
            np.where(
                df["cta_cte"].isin(["130832-12", "334", "Macro", "Patagonia"]),
                "RECUPEROS",
                "OTROS",
            ),
        )

        df = df.groupby(group_by)["importe"].sum()
        df = df.reset_index()
        return df.rename(columns={"importe": "depositos_banco"})

    # -------------------------------------------------
    async def export(self, params: ControlRecursosLiteFilter) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube la hoja ``control_recursos``. NO se genera el archivo Excel
        (patrón ``control_viaticos``): el trabajo pesado corre como tarea
        de fondo para no bloquear el event loop ni agotar el timeout de
        Koyeb.

        Se encola con ``asyncio.create_task`` (y no con ``BackgroundTasks``)
        para ser compatible con la ruta ``/export`` del
        ``GenericRouterFactory``, que no inyecta ``BackgroundTasks``.
        """
        if params.ejercicio is None:
            raise HTTPException(
                status_code=400,
                detail="El parámetro 'ejercicio' es obligatorio para exportar.",
            )
        asyncio.create_task(self._export_to_google_sheets(params))
        return {
            "title": "Exportación a Google Sheets iniciada",
            "detail": (
                "El Google Sheet se actualizará en segundo plano con la hoja: "
                "control_recursos."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_RECURSOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlRecursosLiteFilter
    ) -> None:
        """Tarea de fondo: sube la hoja a Google Sheets.

        NO genera el archivo Excel: solo query + upload, corriendo fuera
        del request. En background no hay respuesta HTTP que retornar: los
        errores se loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlRecursosFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Traemos los datos sin paginar
            data = await self.repository.find_with_filter_params(
                params=search_params
            )
            df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

            # 2. Upload de la hoja (fuera del event loop)
            try:
                await run_in_threadpool(
                    self._build_df_and_upload, df, "control_recursos"
                )
                logger.info(
                    "Control Recursos: hoja 'control_recursos' "
                    "actualizada en Google Sheets"
                )
            except Exception as e:
                logger.error(
                    f"Control Recursos: error al subir la hoja "
                    f"'control_recursos': {e}"
                )
        logger.info("Control Recursos: exportación a Google Sheets finalizada")

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
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_RECURSOS,
        )


ControlRecursosServiceDependency = Annotated[ControlRecursosService, Depends()]
