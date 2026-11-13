__all__ = ["ControlViaticosService", "ControlViaticosServiceDependency"]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...siif.schemas import GtoRpa03gFullFilter, Rfondos04FullFilter
from ...siif.services import GtoRpa03gServiceDependency, Rfondos04ServiceDependency
from ...sscc.schemas import BancoINVICOFullFilter
from ...sscc.services import BancoINVICOServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    upload_multiple_dataframes_to_google_sheets,
    validate_and_extract_data_from_list,
)
from ..repositories.control_viaticos import (
    ControlViaticosRendicionRepositoryDependency,
)
from ..schemas.control_viaticos import (
    ControlViaticosFilter,
    ControlViaticosGenerateFilter,
    ControlViaticosLiteFilter,
    ControlViaticosRendicionDocument,
    ControlViaticosRendicionReport,
)

SPREADSHEET_KEY_CONTROL_VIATICOS: str = "1alo5UBd7YRIBhSXqfo_c5Lz8JBfU3CXrVC0XOmtiH8c"

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlViaticosService(
    BaseService[
        ControlViaticosRendicionReport,
        ControlViaticosRendicionDocument,
        ControlViaticosFilter,
        ControlViaticosLiteFilter,
    ]
):
    control_rendicion_repo: ControlViaticosRendicionRepositoryDependency
    rfondos04_service: Rfondos04ServiceDependency
    gastos_service: GtoRpa03gServiceDependency
    banco_service: BancoINVICOServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base:
        # de ahí salen get_all (Get All / snapshot) y delete_many
        # (Delete) que registra el GenericRouterFactory.
        super().__init__(
            repository=self.control_rendicion_repo,
            filter_schema=ControlViaticosFilter,
        )

    # -------------------------------------------------
    async def add_many(
        self, data: List[ControlViaticosRendicionReport]
    ) -> RouteReturnSchema:
        """Persiste el cruce (snapshot) con borrado idempotente por ejercicio.

        Es la contraparte del ``GET /generate``: el frontend arma el
        cruce on-demand y luego llama aquí para congelarlo en la
        colección ``control_viaticos`` (patrón generate ->
        POST de los demás controles).
        """
        try:
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlViaticosRendicionReport,
                field_id=["ejercicio", "nro_expte"],  # Clave de la fila
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
                repository=self.control_rendicion_repo,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización Control Viáticos Rendición",
                label="Control Viáticos Rendición",
                logger=logger,
            )

        except HTTPException:
            # Respeta el 400 de "sin registros válidos" (no lo envuelve en 500)
            raise
        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self, params: ControlViaticosGenerateFilter
    ) -> List[ControlViaticosRendicionReport]:
        """Cruce Anticipo/Rendición de Viáticos on-demand (sin persistir;
        el snapshot lo congela el POST posterior).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Filas del cruce validadas como ``ControlViaticosRendicionReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlViaticosFilter(ejercicio=params.ejercicio)
        return await self.compute_control_rendicion(params=compute_params)

    # --------------------------------------------------
    async def generate_siif_fondo(self, ejercicio: int) -> pd.DataFrame:
        """SIIF rfondos04: anticipo (PA3) y reversión (REV) del ejercicio.

        Returns:
            DataFrame crudo de rfondos04 sin el id interno de Mongo.
        """
        params = Rfondos04FullFilter(ejercicio=str(ejercicio), limit=None)
        params.set_extra_filter({"tipo_comprobante": {"$in": ["PA3", "REV"]}})
        data = await self.rfondos04_service.get_all(params=params)
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        return df.drop(columns=["id"], errors="ignore")

    # --------------------------------------------------
    async def generate_siif_gastos(self, ejercicio: int) -> pd.DataFrame:
        """SIIF gto_rpa03g unido con rcg01_uejp: partidas 372 (rendición)
        y 373 (reembolso) del ejercicio.

        Returns:
            DataFrame con las columnas de gastos (vacío si no hay datos).
        """
        params = GtoRpa03gFullFilter(ejercicio=str(ejercicio), limit=None)
        params.set_extra_filter({"partida": {"$in": ["372", "373"]}})
        data = await self.gastos_service.get_joined_with_rcg01_uejp(params=params)
        df = pd.DataFrame(data)
        return df.drop(columns=["id"], errors="ignore")

    # --------------------------------------------------
    async def generate_banco(self, ejercicio: int) -> pd.DataFrame:
        """Banco INVICO: pagos de viáticos de la cta_cte 130832-02 con
        imputaciones 029 (anticipo), 040 (reembolso) y 005 (reversión).

        Reproduce la transformación del script original de invicofapy:
        importes con signo negativo y ``nro_expte`` extraído del campo
        ``concepto``.

        Returns:
            DataFrame crudo transformado (vacío si no hay datos).
        """
        params = BancoINVICOFullFilter(ejercicio=str(ejercicio), limit=None)
        params.set_extra_filter(
            {
                "cta_cte": "130832-02",
                "cod_imputacion": {"$in": ["029", "040", "005"]},
            }
        )
        data = await self.banco_service.get_all(params=params)
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        if df.empty:
            return df

        df = df.copy()
        df["importe"] = df["importe"] * (-1)
        df["new_concepto"] = df["concepto"].str.replace(".", "")
        df["nro_expte"] = df["new_concepto"].str.extract(r"EXP\s*(\d+\s*\d+\s*\d+)\s*")[
            0
        ]
        df = df.drop(["new_concepto"], axis=1)
        df["nro_expte"] = df["nro_expte"].apply(self._transform_nro_expte)
        return df

    # --------------------------------------------------
    @staticmethod
    def _transform_nro_expte(x: Any) -> Any:
        """Convierte el expediente extraído al formato 900 + 5 dígitos + año."""
        if not isinstance(x, (str, bytes)) or x is None or x == "":
            return None

        expediente = x.split(" ")
        id_institucion = "900"
        nro_expediente = "00000"
        anio = "0000"
        if len(expediente) >= 2:
            anio = expediente[-1]
            anio = anio if len(anio) == 4 else "20" + anio
            nro_expediente = expediente[-2].zfill(5)
        return f"{id_institucion}{nro_expediente}{anio}"

    # --------------------------------------------------
    async def compute_control_rendicion(
        self, params: ControlViaticosFilter
    ) -> List[dict]:
        """Cruce Anticipo/Rendición de Viáticos on-demand (sin persistir).

        Replica el cómputo del script original de invicofapy: rfondos04
        (PA3/REV) por ``nro_fondo``, gastos 372/373 por ``nro_expte`` y
        movimientos del banco (029/040/005) por ``nro_expte``, con las
        derivadas ``siif_saldo_anticipo``, ``siif_gasto_total`` y
        ``dif_gasto_total``.

        Los lados vacíos se rellenan con columnas sintéticas para que
        los ``merge``/``groupby`` no truenen cuando todavía no hay
        datos crudos de un sistema (mismo criterio que
        ``compute_control_haberes``).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Filas del cruce como lista de dicts (vacía si no hay datos).

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        ejercicio = params.ejercicio
        groupby_cols = ["ejercicio", "nro_expte"]

        # 🔹 SIIF rfondos04 (PA3/REV) agregado por nro_fondo
        siif_fondos = await self.generate_siif_fondo(ejercicio=ejercicio)
        if siif_fondos.empty:
            siif_fondos = pd.DataFrame(
                columns=["nro_fondo", "siif_anticipo", "siif_reversion"]
            )
        else:
            siif_fondos = siif_fondos.copy()
            siif_fondos["siif_anticipo"] = np.where(
                siif_fondos["tipo_comprobante"] == "PA3",
                siif_fondos["importe"],
                0,
            )
            siif_fondos["siif_reversion"] = np.where(
                siif_fondos["tipo_comprobante"] == "REV",
                siif_fondos["importe"],
                0,
            )
            siif_fondos = (
                siif_fondos.groupby(["nro_fondo"])[["siif_anticipo", "siif_reversion"]]
                .sum()
                .reset_index()
            )

        # 🔹 Banco INVICO (029/040/005) agregado por nro_expte
        sscc = await self.generate_banco(ejercicio=ejercicio)
        if sscc.empty:
            sscc = pd.DataFrame(
                columns=[
                    "nro_expte",
                    "sscc_anticipo",
                    "sscc_reversion",
                    "sscc_reembolso",
                    "sscc_gasto_total",
                ]
            )
        else:
            sscc = sscc.copy()
            sscc["sscc_anticipo"] = np.where(
                sscc["cod_imputacion"] == "029", sscc["importe"], 0
            )
            sscc["sscc_reversion"] = np.where(
                sscc["cod_imputacion"] == "005", sscc["importe"], 0
            )
            sscc["sscc_reembolso"] = np.where(
                sscc["cod_imputacion"] == "040", sscc["importe"], 0
            )
            sscc = (
                sscc.groupby(["nro_expte"])[
                    ["sscc_anticipo", "sscc_reversion", "sscc_reembolso"]
                ]
                .sum()
                .reset_index()
            )
            sscc["sscc_gasto_total"] = (
                sscc.sscc_anticipo + sscc.sscc_reversion + sscc.sscc_reembolso
            )

        # 🔹 SIIF gastos (372 rendición / 373 reembolso)
        siif = await self.generate_siif_gastos(ejercicio=ejercicio)
        if siif.empty or "partida" not in siif.columns:
            siif = pd.DataFrame(
                columns=["ejercicio", "nro_expte", "nro_fondo", "partida", "importe"]
            )

        siif_rendicion = siif.loc[siif["partida"] == "372"]
        siif_rendicion = siif_rendicion.rename(columns={"importe": "siif_rendicion"})
        siif_rendicion = (
            siif_rendicion.groupby(groupby_cols + ["nro_fondo"])[["siif_rendicion"]]
            .sum()
            .reset_index()
        )

        df = siif_rendicion.merge(
            siif_fondos, how="left", left_on="nro_fondo", right_on="nro_fondo"
        )
        df = (
            df.groupby(groupby_cols)[
                ["siif_rendicion", "siif_anticipo", "siif_reversion"]
            ]
            .sum()
            .reset_index()
        )

        siif_reembolso = siif.loc[siif["partida"] == "373"]
        siif_reembolso = siif_reembolso.rename(columns={"importe": "siif_reembolso"})
        siif_reembolso = (
            siif_reembolso.groupby(["nro_expte"])[["siif_reembolso"]]
            .sum()
            .reset_index()
        )
        df = df.merge(siif_reembolso, how="left", on="nro_expte")

        df = df.merge(sscc, how="left", on="nro_expte")

        df = (
            df.groupby(groupby_cols)[
                [
                    "siif_anticipo",
                    "siif_rendicion",
                    "siif_reversion",
                    "siif_reembolso",
                    "sscc_anticipo",
                    "sscc_reversion",
                    "sscc_reembolso",
                    "sscc_gasto_total",
                ]
            ]
            .sum()
            .reset_index()
        )
        df["siif_saldo_anticipo"] = (
            df.siif_anticipo - df.siif_reversion - df.siif_rendicion
        )
        df["siif_gasto_total"] = df.siif_rendicion + df.siif_reembolso
        df["dif_gasto_total"] = df["siif_gasto_total"] - df["sscc_gasto_total"]

        if df.empty:
            return []

        df = sanitize_dataframe_for_json_with_datetime(df)
        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlViaticosLiteFilter) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube las hojas ``control_rendicion_db_new`` (snapshot con
        fallback on-demand), ``siif_fondos_db_new`` y
        ``siif_gastos_db_new``. NO se genera el archivo Excel (patrón
        ``control_banco`` / ``control_honorarios``): el trabajo pesado
        corre como tarea de fondo para no bloquear el event loop ni
        agotar el timeout de Koyeb.

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
                "control_rendicion_db_new, siif_fondos_db_new y siif_gastos_db_new."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_VIATICOS,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(self, params: ControlViaticosLiteFilter) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlViaticosFilter(ejercicio=params.ejercicio, limit=None)
        async with _export_lock:
            # 1. Snapshot del cruce (fallback a cómputo on-demand)
            snapshot = await self.get_all(params=search_params)
            control_rendicion = (
                pd.DataFrame([doc.model_dump(by_alias=True) for doc in snapshot])
                if snapshot
                else pd.DataFrame(
                    await self.compute_control_rendicion(params=search_params)
                )
            )

            # 2. Hojas SIIF crudas del mismo ejercicio
            siif_fondos = await self.generate_siif_fondo(ejercicio=params.ejercicio)
            siif_gastos = await self.generate_siif_gastos(ejercicio=params.ejercicio)

            # 3. Upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[pd.DataFrame, str]] = [
                (control_rendicion, "control_rendicion_db_new"),
                (siif_fondos, "siif_fondos_db_new"),
                (siif_gastos, "siif_gastos_db_new"),
            ]
            for df, sheet_name in sheets:
                try:
                    await run_in_threadpool(self._build_df_and_upload, df, sheet_name)
                    logger.info(
                        f"Control Viáticos: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Viáticos: error al subir la hoja '{sheet_name}': {e}"
                    )
        logger.info("Control Viáticos: exportación a Google Sheets finalizada")

    # -------------------------------------------------
    @staticmethod
    def _build_df_and_upload(df: pd.DataFrame, sheet_name: str) -> None:
        """Descarta los id internos y sube la hoja (bloqueante → threadpool).

        NO genera el archivo Excel: solo sube la hoja a Google Sheets.
        """
        df = df.drop(columns=["id", "_id"], errors="ignore")
        upload_multiple_dataframes_to_google_sheets(
            [(df, sheet_name)],
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_VIATICOS,
        )


ControlViaticosServiceDependency = Annotated[ControlViaticosService, Depends()]
