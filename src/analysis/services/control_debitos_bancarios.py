__all__ = ["ControlDebitosBancariosService", "ControlDebitosBancariosServiceDependency"]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...siif.schemas import GtoRpa03gFullFilter
from ...siif.services import GtoRpa03gServiceDependency
from ...sscc.schemas import BancoINVICOFullFilter
from ...sscc.services import BancoINVICOServiceDependency, CtasCtesServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories.control_debitos_bancarios import (
    ControlDebitosBancariosRepositoryDependency,
)
from ..schemas.control_debitos_bancarios import (
    ControlDebitosBancariosDocument,
    ControlDebitosBancariosFilter,
    ControlDebitosBancariosGenerateFilter,
    ControlDebitosBancariosLiteFilter,
    ControlDebitosBancariosReport,
)

SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS: str = (
    "1i9vQ-fw_MkuHRE_YKa_diaVDu5RsiBE1UPTNAsmxLS4"
)

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlDebitosBancariosService(
    BaseService[
        ControlDebitosBancariosReport,
        ControlDebitosBancariosDocument,
        ControlDebitosBancariosFilter,
        ControlDebitosBancariosLiteFilter,
    ]
):
    control_debitos_bancarios_repo: ControlDebitosBancariosRepositoryDependency
    gastos_service: GtoRpa03gServiceDependency
    banco_service: BancoINVICOServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base:
        # de ahí salen get_all (Get All / snapshot) y delete_many
        # (Delete) que registra el GenericRouterFactory.
        super().__init__(
            repository=self.control_debitos_bancarios_repo,
            filter_schema=ControlDebitosBancariosFilter,
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[ControlDebitosBancariosReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce (snapshot) con borrado idempotente por ejercicio.

        Es la contraparte del ``GET /generate``: el frontend arma el
        cruce on-demand y luego llama aquí para congelarlo en la
        colección ``control_debitos_bancarios`` (patrón generate ->
        POST de los demás controles).
        """
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlDebitosBancariosReport,
                field_id=["ejercicio", "mes", "cta_cte"],  # Clave de la fila
            )

            # 🔥 CONTROL CRÍTICO: Si no hay registros válidos, lanzamos un 400 Bad Request.
            # (Asumo que validation_result.validated es una lista vacía o None cuando falla todo)
            if not validation_result.validated:
                # Si validation_result tiene una lista de errores detallados, los exponemos al frontend
                detail_msg = "No se encontraron registros válidos para procesar."
                if hasattr(validation_result, "errors") and validation_result.errors:
                    # Formateamos los primeros errores para no saturar el log pero dar contexto claro
                    detail_msg += f" Errores detectados: {validation_result.errors[:2]}"

                raise HTTPException(status_code=400, detail=detail_msg)

            # 2. Determinar filtro de borrado (Idempotencia)
            # A esta altura ya es 100% seguro que al menos hay un registro válido en el índice [0]
            ejercicio_detectado = validation_result.validated[0].ejercicio
            delete_filter = {"ejercicio": ejercicio_detectado}

            return await sync_validated_to_repository(
                repository=self.control_debitos_bancarios_repo,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Débitos Bancarios",
                label="Control Débitos Bancarios",
                logger=logger,
            )

        except HTTPException:
            # Respeta el 400 de "sin registros válidos" (no lo envuelve en 500)
            raise
        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self, params: ControlDebitosBancariosGenerateFilter
    ) -> List[ControlDebitosBancariosReport]:
        """Cruce Débitos Bancarios SIIF vs SSCC on-demand (sin persistir;
        el snapshot lo congela el POST posterior).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Filas del cruce validadas como
            ``ControlDebitosBancariosReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlDebitosBancariosFilter(ejercicio=params.ejercicio)
        return await self.compute_control_debitos_bancarios(params=compute_params)

    # --------------------------------------------------
    async def generate_siif_debitos(self, ejercicio: int) -> pd.DataFrame:
        """SIIF gto_rpa03g unido con rcg01_uejp: partida 355 (débitos
        bancarios) del ejercicio, con ``cta_cte`` unificada (nexo
        ``siif_gastos_cta_cte``).

        Returns:
            DataFrame de gastos SIIF (vacío si no hay datos).
        """
        params = GtoRpa03gFullFilter(ejercicio=str(ejercicio), limit=None)
        params.set_extra_filter({"partida": {"$in": ["355"]}})
        data = await self.gastos_service.get_joined_with_rcg01_uejp(params=params)
        df = pd.DataFrame(data)
        df = df.drop(columns=["id"], errors="ignore")
        if df.empty:
            return df
        return await self.cta_cte_service.cta_cte_unifier(df, "siif_gastos_cta_cte")

    # --------------------------------------------------
    async def generate_banco_debitos(self, ejercicio: int) -> pd.DataFrame:
        """Banco INVICO: débitos con imputación 031, con ``cta_cte``
        unificada (nexo ``sscc_cta_cte``).

        Returns:
            DataFrame del banco (vacío si no hay datos).
        """
        params = BancoINVICOFullFilter(ejercicio=str(ejercicio), limit=None)
        params.set_extra_filter({"cod_imputacion": {"$in": ["031"]}})
        data = await self.banco_service.get_all(params=params)
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        df = df.drop(columns=["id"], errors="ignore")
        if df.empty:
            return df
        return await self.cta_cte_service.cta_cte_unifier(df, "sscc_cta_cte")

    # --------------------------------------------------
    async def siif_summarize(
        self,
        ejercicio: int,
        groupby_cols: List[str] = ["ejercicio", "mes", "cta_cte"],
    ) -> pd.DataFrame:
        """Suma de importes SIIF (partida 355) por grupo."""
        df = await self.generate_siif_debitos(ejercicio=ejercicio)
        if df.empty or "importe" not in df.columns:
            return pd.DataFrame(columns=groupby_cols + ["importe"])
        df = df.groupby(groupby_cols)["importe"].sum()
        df = df.reset_index()
        df = df.fillna(0)
        return df

    # --------------------------------------------------
    async def sscc_summarize(
        self,
        ejercicio: int,
        groupby_cols: List[str] = ["ejercicio", "mes", "cta_cte"],
    ) -> pd.DataFrame:
        """Suma de importes del banco (imputación 031) por grupo, con
        signo invertido (los débitos llegan negativos)."""
        df = await self.generate_banco_debitos(ejercicio=ejercicio)
        if df.empty or "importe" not in df.columns:
            return pd.DataFrame(columns=groupby_cols + ["importe"])
        df = df.groupby(groupby_cols)["importe"].sum()
        df = df.reset_index()
        df["importe"] = df["importe"] * -1
        return df

    # --------------------------------------------------
    async def compute_control_debitos_bancarios(
        self,
        params: ControlDebitosBancariosFilter,
        only_diff: bool = False,
    ) -> List[dict]:
        """Cruce Débitos Bancarios SIIF vs SSCC on-demand (sin persistir).

        Replica el cómputo del script original de invicofapy: resúmenes
        por ``[ejercicio, mes, cta_cte]`` de la partida 355 SIIF y de la
        imputación 031 del banco, con ``diferencia =
        ejecutado_siif - debitos_sscc``.

        Los lados vacíos se rellenan con columnas sintéticas para que
        los ``set_index``/``merge``/``reindex`` no truenen cuando
        todavía no hay datos crudos de un sistema.

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.
            only_diff: Si es True, devuelve solo las filas con
                diferencia material (``|suma| > 0.01``).

        Returns:
            Filas del cruce como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio = params.ejercicio
        groupby_cols = ["ejercicio", "mes", "cta_cte"]

        siif = await self.siif_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        siif = siif.rename(columns={"importe": "ejecutado_siif"})
        siif = siif.set_index(groupby_cols)

        sscc = await self.sscc_summarize(ejercicio=ejercicio, groupby_cols=groupby_cols)
        sscc = sscc.rename(columns={"importe": "debitos_sscc"})
        sscc = sscc.set_index(groupby_cols)

        # Obtener los índices faltantes en siif
        missing_indices = sscc.index.difference(siif.index)
        # Reindexar el DataFrame siif con los índices faltantes
        siif = siif.reindex(siif.index.union(missing_indices))
        sscc = sscc.reindex(siif.index)
        siif = siif.fillna(0)
        sscc = sscc.fillna(0)
        df = siif.merge(sscc, how="outer", on=groupby_cols)
        df = df.reset_index()
        df = df.fillna(0)
        df["diferencia"] = df["ejecutado_siif"] - df["debitos_sscc"]

        if only_diff:
            numeric_cols = df.select_dtypes(include=np.number).columns.drop("ejercicio")
            df = df[np.abs(df[numeric_cols].sum(axis=1)) > 0.01]
            df = df.reset_index(drop=True)

        if df.empty:
            return []

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlDebitosBancariosLiteFilter) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube las hojas ``siif_vs_sscc_db`` (snapshot con fallback
        on-demand), ``siif_db`` y ``sscc_db``. NO se genera el archivo
        Excel (patrón ``control_banco`` / ``control_viaticos``): el
        trabajo pesado corre como tarea de fondo para no bloquear el
        event loop ni agotar el timeout de Koyeb.

        Se encola con ``asyncio.create_task`` (y no con
        ``BackgroundTasks``) para ser compatible con la ruta ``/export``
        del ``GenericRouterFactory``, que no inyecta ``BackgroundTasks``.
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
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "siif_vs_sscc_db, siif_db y sscc_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlDebitosBancariosLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlDebitosBancariosFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,
        )
        async with _export_lock:
            # 1. Snapshot del cruce (fallback a cómputo on-demand)
            snapshot = await self.get_all(params=search_params)
            control_debitos = (
                pd.DataFrame([doc.model_dump(by_alias=True) for doc in snapshot])
                if snapshot
                else pd.DataFrame(
                    await self.compute_control_debitos_bancarios(params=search_params)
                )
            )

            # 2. Hojas crudas del mismo ejercicio
            siif = await self.generate_siif_debitos(ejercicio=params.ejercicio)
            sscc = await self.generate_banco_debitos(ejercicio=params.ejercicio)

            # 3. Upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[pd.DataFrame, str]] = [
                (control_debitos, "siif_vs_sscc_db"),
                (siif, "siif_db"),
                (sscc, "sscc_db"),
            ]
            for df, sheet_name in sheets:
                try:
                    await run_in_threadpool(self._build_df_and_upload, df, sheet_name)
                    logger.info(
                        f"Control Débitos Bancarios: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        "Control Débitos Bancarios: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info("Control Débitos Bancarios: exportación a Google Sheets finalizada")

    # -------------------------------------------------
    @staticmethod
    def _build_df_and_upload(df: pd.DataFrame, sheet_name: str) -> None:
        """Descarta los id internos y sube la hoja (bloqueante → threadpool).

        NO genera el archivo Excel: solo sube la hoja a Google Sheets.
        """
        df = df.drop(columns=["id", "_id"], errors="ignore")
        upload_multiple_dataframes_to_google_sheets(
            [(df, sheet_name)],
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_DEBITOS_BANCIARIOS,
        )


ControlDebitosBancariosServiceDependency = Annotated[
    ControlDebitosBancariosService, Depends()
]
