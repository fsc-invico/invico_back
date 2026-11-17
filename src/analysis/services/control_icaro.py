__all__ = ["ControlIcaroService", "ControlIcaroServiceDependency"]

# import os
import asyncio
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, Any

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...icaro.schemas import CargaFullFilter
from ...icaro.services import CargaServiceDependency
from ...siif.schemas import (
    GtoRpa03gFullFilter,
    Rf602FullFilter,
    Rfondo07tpFullFilter,
)
from ...siif.services import (
    GtoRpa03gServiceDependency,
    Rf602ServiceDependency,
    Rfondo07tpServiceDependency,
)

# from pydantic import ValidationError
from ...utils import (
    sanitize_dataframe_for_json_with_datetime,
    upload_multiple_dataframes_to_google_sheets,
)
from ..schemas import (
    ControlIcaroFullFilter,
    ControlIcaroLiteFilter,
)

SPREADSHEET_KEY_CONTROL_ICARO: str = (
    "1KKeeoop_v_Nf21s7eFp4sS6SmpxRZQ9DPa1A5wVqnZ0"
)

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlIcaroService:
    gastos_service: GtoRpa03gServiceDependency
    icaro_service: CargaServiceDependency
    rf602_service: Rf602ServiceDependency
    rfondo07tp_service: Rfondo07tpServiceDependency

    # -------------------------------------------------
    async def get_siif_gastos(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        gastos_params.set_extra_filter({"partida": {"$in": ["421", "422", "354"]}})

        data = await self.gastos_service.get_joined_with_rcg01_uejp(
            params=gastos_params
        )
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 3. Filtrado exacto equivalente al método de Pandas
        df = df.loc[
            (df["partida"].isin(["421", "422"]))
            | (
                (df["partida"] == "354")
                & (
                    ~df["cuit"]
                    .astype(str)
                    .isin(["30500049460", "30632351514", "20231243527"])
                )
            )
        ]

        # 4. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 5. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_icaro_comprobantes(
        self,
        params: ControlIcaroFullFilter,
        exclude_pa6: bool = False,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        icaro_params = CargaFullFilter(
            query_filter="tipo!=PA6" if exclude_pa6 else "",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.icaro_service.get_all(params=icaro_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe
        df["estructura"] = df.actividad + "-" + df.partida

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_siif_obras(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        rf602_params = Rf602FullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        rf602_params.set_extra_filter(
            {
                "$or": [
                    {"partida": {"$in": ["421", "422"]}},
                    {"estructura": "01-00-00-03-354"},
                ]
            }
        )

        data = await self.rf602_service.with_desc_estructuras(params=rf602_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame(data)

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_siif_pa6(
        self,
        params: ControlIcaroFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        rfondo07tp_params = Rfondo07tpFullFilter(
            tipo_comprobante="PA6",
            ejercicio=str(params.ejercicio),
            limit=None,
        )

        data = await self.rfondo07tp_service.get_all(params=rfondo07tp_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 3. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_anual(
        self,
        params: ControlIcaroFullFilter,
        icaro: list[dict] = None,
        siif: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "estructura", "fuente"]

        if not icaro:
            icaro = await self.get_icaro_comprobantes(params=params, exclude_pa6=True)
        icaro = pd.DataFrame(icaro)
        icaro = icaro.loc[icaro["tipo"] != "PA6"]
        icaro = icaro.groupby(groupby_cols)["importe"].sum()
        icaro = icaro.reset_index()
        icaro = icaro.rename(columns={"importe": "ejecucion_icaro"})
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not siif:
            siif = await self.get_siif_obras(params=params)
        siif = pd.DataFrame(siif)
        siif = siif.loc[
            :,
            groupby_cols
            + [
                "ordenado",
                "desc_programa",
                "desc_subprograma",
                "desc_proyecto",
                "desc_actividad",
            ],
        ]
        siif = siif.rename(columns={"ordenado": "ejecucion_siif"})
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(siif, icaro, how="outer", on=groupby_cols)
        # Solo las columnas de importes se rellenan con 0: los desc_* de
        # las filas que vienen solo de ICARO quedan en NaN y deben
        # persistirse como None (Pydantic no admite int en Optional[str]).
        df[["ejecucion_siif", "ejecucion_icaro"]] = df[
            ["ejecucion_siif", "ejecucion_icaro"]
        ].fillna(0)
        df["diferencia"] = df["ejecucion_siif"] - df["ejecucion_icaro"]

        df = df.loc[(df["diferencia"] < -0.2) | (df["diferencia"] > 0.2)]
        df = df.reset_index(drop=True)
        df["fuente"] = pd.to_numeric(df["fuente"], errors="coerce")
        df["ejercicio"] = pd.to_numeric(df["ejercicio"], errors="coerce")

        df = df.loc[
            :,
            [
                "ejercicio",
                "estructura",
                "fuente",
                "ejecucion_siif",
                "ejecucion_icaro",
                "diferencia",
                "desc_actividad",
                "desc_programa",
                "desc_subprograma",
                "desc_proyecto",
            ],
        ]

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_comprobantes(
        self,
        params: ControlIcaroFullFilter,
        siif: list[dict] = None,
        icaro: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        select = [
            "ejercicio",
            "nro_comprobante",
            "fuente",
            "importe",
            "mes",
            "cta_cte",
            "cuit",
            "partida",
        ]

        if not siif:
            siif = await self.get_siif_gastos(params=params)
        siif = pd.DataFrame(siif)
        siif.loc[(siif.clase_reg == "REG") & (siif.nro_fondo.isnull()), "clase_reg"] = (
            "CYO"
        )
        siif = siif.loc[:, select + ["clase_reg"]]
        siif = siif.rename(
            columns={
                "nro_comprobante": "siif_nro",
                "clase_reg": "siif_tipo",
                "fuente": "siif_fuente",
                "importe": "siif_importe",
                "mes": "siif_mes",
                "cta_cte": "siif_cta_cte",
                "cuit": "siif_cuit",
                "partida": "siif_partida",
            }
        )
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not icaro:
            icaro = await self.get_icaro_comprobantes(params=params, exclude_pa6=True)
        icaro = pd.DataFrame(icaro)
        icaro = icaro.loc[icaro["tipo"] != "PA6"]
        icaro = icaro.loc[:, select + ["tipo"]]
        icaro = icaro.rename(
            columns={
                "nro_comprobante": "icaro_nro",
                "tipo": "icaro_tipo",
                "fuente": "icaro_fuente",
                "importe": "icaro_importe",
                "mes": "icaro_mes",
                "cta_cte": "icaro_cta_cte",
                "cuit": "icaro_cuit",
                "partida": "icaro_partida",
            }
        )
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(
            siif,
            icaro,
            how="outer",
            left_on=["ejercicio", "siif_nro"],
            right_on=["ejercicio", "icaro_nro"],
        )
        df["err_nro"] = df.siif_nro != df.icaro_nro
        df["err_tipo"] = df.siif_tipo != df.icaro_tipo
        df["err_mes"] = df.siif_mes != df.icaro_mes
        df["err_partida"] = df.siif_partida != df.icaro_partida
        df["err_fuente"] = df.siif_fuente != df.icaro_fuente
        df["siif_importe"] = df["siif_importe"].fillna(0)
        df["icaro_importe"] = df["icaro_importe"].fillna(0)
        df["err_importe"] = (df.siif_importe - df.icaro_importe).abs()
        df["err_importe"] = df["err_importe"] > 0.1
        df["err_cta_cte"] = df.siif_cta_cte != df.icaro_cta_cte
        df["err_cuit"] = df.siif_cuit != df.icaro_cuit
        df = df.loc[
            (
                df.err_nro
                + df.err_tipo
                + df.err_mes
                + df.err_partida
                + df.err_fuente
                + df.err_importe
                + df.err_cta_cte
                + df.err_cuit
            )
            > 0
        ]

        df = sanitize_dataframe_for_json_with_datetime(df)
        df = df.loc[
            :,
            [
                "ejercicio",
                "siif_nro",
                "icaro_nro",
                "err_nro",
                "siif_tipo",
                "icaro_tipo",
                "err_tipo",
                "siif_fuente",
                "icaro_fuente",
                "err_fuente",
                "siif_importe",
                "icaro_importe",
                "err_importe",
                "siif_mes",
                "icaro_mes",
                "err_mes",
                "siif_cta_cte",
                "icaro_cta_cte",
                "err_cta_cte",
                "siif_cuit",
                "icaro_cuit",
                "err_cuit",
                "siif_partida",
                "icaro_partida",
                "err_partida",
            ],
        ]

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_pa6(
        self,
        params: ControlIcaroFullFilter,
        siif_fdos: list[dict] = None,
        siif_gtos: list[dict] = None,
        icaro: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        if not siif_fdos:
            siif_fdos = await self.get_siif_pa6(params=params)
        siif_fdos = pd.DataFrame(siif_fdos)
        siif_fdos = siif_fdos.loc[
            :, ["ejercicio", "nro_fondo", "mes", "ingresos", "saldo"]
        ]
        siif_fdos["nro_fondo"] = (
            siif_fdos["nro_fondo"].str.zfill(5) + "/" + siif_fdos.mes.str[-2:]
        )
        siif_fdos = siif_fdos.rename(
            columns={
                "nro_fondo": "siif_nro_fondo",
                "mes": "siif_mes_pa6",
                "ingresos": "siif_importe_pa6",
                "saldo": "siif_saldo_pa6",
            }
        )
        siif_fdos.dropna(subset=["siif_nro_fondo"], inplace=True)
        # print(
        #     f"siif_fdos.info: {siif_fdos.info()} - siif_fdos.head: {siif_fdos.head()}"
        # )

        select = [
            "ejercicio",
            "nro_comprobante",
            "fuente",
            "importe",
            "mes",
            "cta_cte",
            "cuit",
        ]

        if not siif_gtos:
            siif_gtos = await self.get_siif_gastos(params=params)
        siif_gtos = pd.DataFrame(siif_gtos)
        siif_gtos = siif_gtos.loc[siif_gtos["clase_reg"] == "REG"]
        siif_gtos = siif_gtos.loc[:, select + ["nro_fondo", "clase_reg"]]
        siif_gtos["nro_fondo"] = (
            siif_gtos["nro_fondo"].str.zfill(5) + "/" + siif_gtos.mes.str[-2:]
        )
        siif_gtos = siif_gtos.rename(
            columns={
                "nro_fondo": "siif_nro_fondo",
                "cta_cte": "siif_cta_cte",
                "cuit": "siif_cuit",
                "clase_reg": "siif_tipo",
                "fuente": "siif_fuente",
                "nro_comprobante": "siif_nro_reg",
                "importe": "siif_importe_reg",
                "mes": "siif_mes_reg",
            }
        )
        siif_gtos.dropna(subset=["siif_nro_fondo"], inplace=True)
        # print(
        #     f"siif_gtos.info: {siif_gtos.info()} - siif_gtos.head: {siif_gtos.head()}"
        # )

        if not icaro:
            icaro = await self.get_icaro_comprobantes(params=params, exclude_pa6=False)
        icaro = pd.DataFrame(icaro)
        icaro = icaro.loc[:, select + ["tipo"]]
        icaro = icaro.rename(
            columns={
                "mes": "icaro_mes",
                "nro_comprobante": "icaro_nro",
                "tipo": "icaro_tipo",
                "importe": "icaro_importe",
                "cuit": "icaro_cuit",
                "cta_cte": "icaro_cta_cte",
                "fuente": "icaro_fuente",
            }
        )

        icaro_pa6 = icaro.loc[icaro["icaro_tipo"] == "PA6"]
        icaro_pa6 = icaro_pa6.loc[
            :, ["ejercicio", "icaro_mes", "icaro_nro", "icaro_importe"]
        ]
        icaro_pa6 = icaro_pa6.rename(
            columns={
                "icaro_mes": "icaro_mes_pa6",
                "icaro_nro": "icaro_nro_fondo",
                "icaro_importe": "icaro_importe_pa6",
            }
        )

        icaro_reg = icaro.loc[icaro["icaro_tipo"] != "PA6"]
        icaro_reg = icaro_reg.rename(
            columns={
                "icaro_mes": "icaro_mes_reg",
                "icaro_nro": "icaro_nro_reg",
                "icaro_importe": "icaro_importe_reg",
            }
        )

        df = pd.merge(
            siif_fdos,
            siif_gtos,
            how="left",
            on=["ejercicio", "siif_nro_fondo"],
        )

        df = pd.merge(
            df,
            icaro_pa6,
            how="outer",
            left_on=["ejercicio", "siif_nro_fondo"],
            right_on=["ejercicio", "icaro_nro_fondo"],
        )

        df = pd.merge(
            df,
            icaro_reg,
            how="left",
            left_on=["ejercicio", "siif_nro_reg"],
            right_on=["ejercicio", "icaro_nro_reg"],
        )

        # df = df.fillna(0)
        df["err_nro_fondo"] = (df.siif_nro_fondo != df.icaro_nro_fondo) & ~(
            df.siif_nro_fondo.isna() & df.icaro_nro_fondo.isna()
        )
        df["err_mes_pa6"] = (df.siif_mes_pa6 != df.icaro_mes_pa6) & ~(
            df.siif_mes_pa6.isna() & df.icaro_mes_pa6.isna()
        )
        df["siif_importe_pa6"] = df["siif_importe_pa6"].fillna(0)
        df["icaro_importe_pa6"] = df["icaro_importe_pa6"].fillna(0)
        df["err_importe_pa6"] = (df.siif_importe_pa6 - df.icaro_importe_pa6).abs()
        df["err_importe_pa6"] = df["err_importe_pa6"] > 0.1
        # df['err_importe_pa6'] = ~np.isclose((df.siif_importe_pa6 - df.icaro_importe_pa6), 0)
        df["err_nro_reg"] = (df.siif_nro_reg != df.icaro_nro_reg) & ~(
            df.siif_nro_reg.isna() & df.icaro_nro_reg.isna()
        )
        df["err_mes_reg"] = (df.siif_mes_reg != df.icaro_mes_reg) & ~(
            df.siif_mes_reg.isna() & df.icaro_mes_reg.isna()
        )
        df["siif_importe_reg"] = df["siif_importe_reg"].fillna(0)
        df["icaro_importe_reg"] = df["icaro_importe_reg"].fillna(0)
        df["err_importe_reg"] = (df.siif_importe_reg - df.icaro_importe_reg).abs()
        df["err_importe_reg"] = df["err_importe_reg"] > 0.1
        # df['err_importe_reg'] = ~np.isclose((df.siif_importe_reg - df.icaro_importe_reg), 0)
        df["err_tipo"] = (df.siif_tipo != df.icaro_tipo) & ~(
            df.siif_tipo.isna() & df.icaro_tipo.isna()
        )
        df["err_fuente"] = (df.siif_fuente != df.icaro_fuente) & ~(
            df.siif_fuente.isna() & df.icaro_fuente.isna()
        )
        df["err_cta_cte"] = (df.siif_cta_cte != df.icaro_cta_cte) & ~(
            df.siif_cta_cte.isna() & df.icaro_cta_cte.isna()
        )
        df["err_cuit"] = (df.siif_cuit != df.icaro_cuit) & ~(
            df.siif_cuit.isna() & df.icaro_cuit.isna()
        )
        # cols = list(ControlPa6Report.model_fields.keys())
        # df = df[cols]
        df = df.loc[
            (
                df.err_nro_fondo
                + df.err_mes_pa6
                + df.err_importe_pa6
                + df.err_nro_reg
                + df.err_mes_reg
                + df.err_importe_reg
                + df.err_fuente
                + df.err_tipo
                + df.err_cta_cte
                + df.err_cuit
            )
            > 0
        ]

        df = df.sort_values(
            by=[
                "err_nro_fondo",
                "err_importe_pa6",
                "err_nro_reg",
                "err_importe_reg",
                "err_fuente",
                "err_cta_cte",
                "err_cuit",
                "err_tipo",
                "err_mes_pa6",
                "err_mes_reg",
            ],
            ascending=False,
        )

        df = sanitize_dataframe_for_json_with_datetime(df)

        df = df.loc[
            :,
            [
                "ejercicio",
                "siif_nro_fondo",
                "icaro_nro_fondo",
                "err_nro_fondo",
                "siif_mes_pa6",
                "icaro_mes_pa6",
                "err_mes_pa6",
                "siif_importe_pa6",
                "icaro_importe_pa6",
                "err_importe_pa6",
                "siif_nro_reg",
                "icaro_nro_reg",
                "err_nro_reg",
                "siif_mes_reg",
                "icaro_mes_reg",
                "err_mes_reg",
                "siif_importe_reg",
                "icaro_importe_reg",
                "err_importe_reg",
                "siif_tipo",
                "icaro_tipo",
                "err_tipo",
                "siif_fuente",
                "icaro_fuente",
                "err_fuente",
                "siif_cta_cte",
                "icaro_cta_cte",
                "err_cta_cte",
                "siif_cuit",
                "icaro_cuit",
                "err_cuit",
            ],
        ]

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlIcaroLiteFilter) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube las hojas ``control_ejecucion_anual_db``,
        ``control_comprobantes_db``, ``control_pa6_db``,
        ``siif_comprobantes_db``, ``siif_obras_db``, ``siif_pa6_db`` e
        ``icaro_comprobantes_db`` (los 3 subreportes/pestañas). NO se
        genera el archivo Excel (patrón ``control_viaticos``): el trabajo
        pesado corre como tarea de fondo para no bloquear el event loop ni
        agotar el timeout de Koyeb.

        Se encola con ``asyncio.create_task`` (y no con ``BackgroundTasks``)
        para ser compatible con la ruta ``/export``, que no inyecta
        ``BackgroundTasks``.
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
                "control_ejecucion_anual_db, control_comprobantes_db, "
                "control_pa6_db, siif_comprobantes_db, siif_obras_db, "
                "siif_pa6_db e icaro_comprobantes_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_ICARO,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlIcaroLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        NO genera el archivo Excel (a diferencia del export binario
        anterior): solo queries + upload, corriendo fuera del request.
        Procesa de a una hoja para mantener el pico de memoria acotado
        (Koyeb dispone de poca RAM en su capa gratuita).

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlIcaroFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Crudos SIIF + ICARO
            data_siif_comprobantes = await self.get_siif_gastos(
                params=search_params
            )
            data_siif_obras = await self.get_siif_obras(params=search_params)
            data_siif_pa6 = await self.get_siif_pa6(params=search_params)
            data_icaro_comprobantes = await self.get_icaro_comprobantes(
                params=search_params, exclude_pa6=False
            )

            # 2. Cruces de los 3 subreportes con los crudos ya leídos
            data_ctrl_anual = await self.compute_control_anual(
                params=search_params,
                icaro=data_icaro_comprobantes,
                siif=data_siif_obras,
            )
            data_ctrl_comprobantes = await self.compute_control_comprobantes(
                params=search_params,
                icaro=data_icaro_comprobantes,
                siif=data_siif_comprobantes,
            )
            data_ctrl_pa6 = await self.compute_control_pa6(
                params=search_params,
                icaro=data_icaro_comprobantes,
                siif_fdos=data_siif_pa6,
                siif_gtos=data_siif_comprobantes,
            )

            # 3. DataFrames + upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[pd.DataFrame, str]] = [
                (pd.DataFrame(data_ctrl_anual), "control_ejecucion_anual_db"),
                (
                    pd.DataFrame(data_ctrl_comprobantes),
                    "control_comprobantes_db",
                ),
                (pd.DataFrame(data_ctrl_pa6), "control_pa6_db"),
                (pd.DataFrame(data_siif_comprobantes), "siif_comprobantes_db"),
                (pd.DataFrame(data_siif_obras), "siif_obras_db"),
                (pd.DataFrame(data_siif_pa6), "siif_pa6_db"),
                (
                    pd.DataFrame(data_icaro_comprobantes),
                    "icaro_comprobantes_db",
                ),
            ]
            for df, sheet_name in sheets:
                try:
                    await run_in_threadpool(
                        self._build_df_and_upload, df, sheet_name
                    )
                    logger.info(
                        f"Control Icaro: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Icaro: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info("Control Icaro: exportación a Google Sheets finalizada")

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
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_ICARO,
        )


ControlIcaroServiceDependency = Annotated[ControlIcaroService, Depends()]
