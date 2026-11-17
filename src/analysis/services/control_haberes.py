__all__ = [
    "ControlHaberesService",
    "ControlHaberesServiceDependency",
]

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any, List

import numpy as np
import pandas as pd
from fastapi import Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ...config import logger
from ...siif.schemas import GtoRpa03gFullFilter, Rcocc31FullFilter, Rdeu012FullFilter
from ...siif.services import (
    GtoRpa03gServiceDependency,
    Rcocc31ServiceDependency,
    Rdeu012ServiceDependency,
)
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
from ..repositories import ControlHaberesRepositoryDependency
from ..schemas import (
    ControlHaberesDocument,
    ControlHaberesFullFilter,
    ControlHaberesGenerateFilter,
    ControlHaberesLiteFilter,
    ControlHaberesReport,
)

SPREADSHEET_KEY_CONTROL_HABERES: str = (
    "1A9ypUkwm4kfLqUAwr6-55crcFElisOO9fOdI6iflMAc"
)

# Serializa las exportaciones para que dos tareas simultáneas no
# intercaleen sus chunks dentro de la misma hoja.
_export_lock: asyncio.Lock = asyncio.Lock()


@dataclass
# -------------------------------------------------
class ControlHaberesService(
    BaseService[
        ControlHaberesReport,
        ControlHaberesDocument,
        ControlHaberesFullFilter,
        ControlHaberesLiteFilter,
    ]
):
    repository: ControlHaberesRepositoryDependency
    gastos_service: GtoRpa03gServiceDependency
    rdeu_service: Rdeu012ServiceDependency
    contabilidad_service: Rcocc31ServiceDependency
    cta_cte_service: CtasCtesServiceDependency
    banco_service: BancoINVICOServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ControlHaberesFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ControlHaberesReport]) -> RouteReturnSchema:
        """Persiste el cruce (snapshot) con borrado idempotente por ejercicio.

        Es la contraparte del ``GET /generate``: el frontend arma el
        cruce on-demand y luego llama aquí para congelarlo en la colección
        ``control_haberes`` (patrón generate -> POST de control_recursos /
        control_obras).
        """
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ControlHaberesReport,
                field_id=[
                    "ejercicio",
                    "mes",
                ],  # Clave de la fila del cruce mensual
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
                title="Sincronización Control Haberes",
                label="Control Haberes",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def generate(
        self,
        params: ControlHaberesGenerateFilter,
    ) -> List[ControlHaberesReport]:
        """Cruce mensual Haberes SIIF vs Banco INVICO (on-demand).

        Replica el cómputo que la página ejecutaba en ``GET /compute``:
        suma del ejecutado SIIF y del pagado en SSCC por
        ``[ejercicio, mes]``, la diferencia y su acumulado.

        Lee las colecciones crudas directamente de MongoDB sin
        descargarlas al cliente. El resultado es una vista on-demand: el
        snapshot en la colección ``control_haberes`` lo congela el
        frontend con el ``POST`` posterior (patrón generate -> POST de
        control_recursos).

        Args:
            params: Filtro con el ``ejercicio`` a recalcular.

        Returns:
            Lista de filas del cruce validadas como
            ``ControlHaberesReport``.

        Raises:
            ValueError: Si falta el parámetro ``ejercicio``.
        """
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        compute_params = ControlHaberesFullFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        return await self.compute_control_haberes(params=compute_params)

    # -------------------------------------------------
    async def get_siif_comprobantes_haberes_neto_rdeu(
        self,
        params: ControlHaberesFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            ejercicio=str(params.ejercicio),
            limit=None,
        )
        gastos_params.set_extra_filter({"partida": {"$nin": ["150", "151"]}})

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

        # 3. Filtramos la cuenta 130830-04
        df = df.loc[df["cta_cte"] == "130832-04"]
        df["grupo"] = df["grupo"] + "00"
        df = df.loc[
            :,
            [
                "ejercicio",
                "mes",
                "fecha",
                "nro_comprobante",
                "importe",
                "grupo",
                "partida",
                "nro_entrada",
                "nro_origen",
                "nro_expte",
                "glosa",
                "beneficiario",
                "nro_fondo",
                "fuente",
                "cta_cte",
                "cuit",
                "clase_reg",
                "clase_mod",
                "clase_gto",
                "es_comprometido",
                "es_verificado",
                "es_aprobado",
                "es_pagado",
            ],
        ]

        # 4. Neteamos código 310 y gcias
        contabilidad_params = Rcocc31FullFilter(
            ejercicio=str(params.ejercicio),
            cta_contable="2122-1-2",
            limit=None,
        )
        contabilidad_params.set_extra_filter(
            {
                "auxiliar_1": {"$in": ["245", "310"]},
                "tipo_comprobante": {"$nin": ["APE", "CIE"]},
            }
        )
        gcias_310 = await self.contabilidad_service.get_all(params=contabilidad_params)
        if gcias_310:
            gcias_310 = pd.DataFrame([d.model_dump(by_alias=True) for d in gcias_310])
            gcias_310["nro_comprobante"] = (
                gcias_310["nro_original"].str.zfill(5)
                + "/"
                + gcias_310["ejercicio"].astype(str).str[-2:]
                + "A"
            )
            gcias_310["importe"] = gcias_310["creditos"] * (-1)
            gcias_310["grupo"] = "100"
            gcias_310["partida"] = gcias_310["auxiliar_1"]
            gcias_310["nro_origen"] = gcias_310["nro_entrada"]
            gcias_310["nro_expte"] = "90000000" + gcias_310["ejercicio"].astype(str)
            gcias_310["glosa"] = np.where(
                gcias_310["auxiliar_1"] == "245",
                "RET. GCIAS. 4TA CATEGORÍA",
                "HABERES ERRONEOS COD 310",
            )
            gcias_310["beneficiario"] = "INSTITUTO DE VIVIENDA DE CORRIENTES"
            gcias_310["nro_fondo"] = None
            gcias_310["fuente"] = "11"
            gcias_310["cta_cte"] = "130832-04"
            gcias_310["cuit"] = "30632351514"
            gcias_310["clase_reg"] = "CYO"
            gcias_310["clase_mod"] = "NOR"
            gcias_310["clase_gto"] = "REM"
            gcias_310["es_comprometido"] = True
            gcias_310["es_verificado"] = True
            gcias_310["es_aprobado"] = True
            gcias_310["es_pagado"] = True
            gcias_310 = gcias_310.loc[
                :,
                [
                    "ejercicio",
                    "mes",
                    "fecha",
                    "nro_comprobante",
                    "importe",
                    "grupo",
                    "partida",
                    "nro_entrada",
                    "nro_origen",
                    "nro_expte",
                    "glosa",
                    "beneficiario",
                    "nro_fondo",
                    "fuente",
                    "cta_cte",
                    "cuit",
                    "clase_reg",
                    "clase_mod",
                    "clase_gto",
                    "es_comprometido",
                    "es_verificado",
                    "es_aprobado",
                    "es_pagado",
                ],
            ]
            df = pd.concat([df, gcias_310])

        # 5. Traemos la deuda flotante filtrada
        rdeu_params = Rdeu012FullFilter(
            query_filter="cta_cte=130832-04, glosa~^(?!.*ART)",
            limit=None,
        )
        # Obtenemos los meses a descargar
        meses = [f"12/{str(params.ejercicio - 1)}"]
        for mes in range(1, 13):
            periodo_str = f"{mes:02d}/{str(params.ejercicio)}"
            meses.append(periodo_str)

        rdeu_params.set_extra_filter({"mes_hasta": {"$in": meses}})

        data_rdeu = await self.rdeu_service.get_all(params=rdeu_params)
        if data_rdeu:
            rdeu = pd.DataFrame([d.model_dump(by_alias=True) for d in data_rdeu])
            rdeu = rdeu.drop(
                columns=["id"], errors="ignore"
            )  # Eliminar la columna 'id' si existe
            rdeu = rdeu.sort_values(by=["fecha_hasta"])

            # Detectamos los comprobantes que quedaron impagos y le cambiamos el signo
            registros_impagos = pd.merge(
                df.drop_duplicates(subset=["nro_comprobante"]),
                rdeu.loc[
                    :, ["nro_comprobante", "saldo", "fecha_hasta", "mes_hasta"]
                ].drop_duplicates(subset=["nro_comprobante", "saldo"], keep="first"),
                how="inner",
                on="nro_comprobante",
            )
            registros_impagos["importe"] = registros_impagos["saldo"] * (-1)
            registros_impagos["fecha"] = registros_impagos["fecha_hasta"]
            registros_impagos["mes"] = registros_impagos["mes_hasta"]
            registros_impagos["clase_gto"] = "RDEU"
            registros_impagos = registros_impagos.drop(
                columns=["grupo", "partida", "saldo", "mes_hasta", "fecha_hasta"],
                errors="ignore",
            )
            df = pd.concat([df, registros_impagos], ignore_index=True)

            # Ajustamos la Deuda Flotante Pagada
            rdeu = rdeu.drop_duplicates(
                subset=["nro_comprobante", "saldo"], keep="last"
            )
            rdeu["fecha_hasta"] = rdeu["fecha_hasta"] + pd.tseries.offsets.DateOffset(
                months=1
            )
            rdeu["mes_hasta"] = rdeu["fecha_hasta"].dt.strftime("%m/%Y")
            rdeu["ejercicio"] = pd.to_numeric(rdeu["mes_hasta"].str[-4:])
            rdeu = rdeu.loc[rdeu["ejercicio"] == int(params.ejercicio)]
            rdeu["clase_reg"] = "CYO"
            rdeu["clase_mod"] = "NOR"
            rdeu["clase_gto"] = "RDEU"
            rdeu["es_comprometido"] = True
            rdeu["es_verificado"] = True
            rdeu["es_aprobado"] = True
            rdeu["es_pagado"] = True
            rdeu = rdeu.drop(
                columns=[
                    "fecha",
                    "mes",
                    "importe",
                    "fecha_aprobado",
                    "fecha_desde",
                    "org_fin",
                ]
            )
            rdeu = rdeu.rename(
                columns={"fecha_hasta": "fecha", "mes_hasta": "mes", "saldo": "importe"}
            )
            df = pd.concat([df, rdeu], ignore_index=True)
            df = df.fillna("")

        # 6. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 7. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def get_banco_invico(
        self,
        params: ControlHaberesFullFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        banco_params = BancoINVICOFullFilter(
            query_filter="cta_cte=130832-04, movimiento!=DEPOSITO",
            ejercicio=str(params.ejercicio),
            limit=None,
        )
        dep_transf_int = ["034", "004"]
        dep_otros = ["003", "055", "005", "013"]
        banco_params.set_extra_filter(
            {"cod_imputacion": {"$nin": dep_transf_int + dep_otros}}
        )

        data = await self.banco_service.get_all(params=banco_params)
        if not data:
            return []

        # 1. Carga eficiente a DataFrame
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        df = df.drop(
            columns=["id"], errors="ignore"
        )  # Eliminar la columna 'id' si existe

        # 2. Cambiamos el signo de importe
        df["importe"] = df["importe"] * (-1)

        # 3. Filtramos los registros de Impuestos a las Ganancias
        keep = ["GCIAS", "GANANCIAS"]
        df = df.loc[~df.concepto.str.contains("|".join(keep))]

        # 4. Aplicamos el limite a la cantidad de registros, si existe
        if params.limit is not None and params.limit > 0:
            df = df.head(params.limit)

        # 5. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def compute_control_haberes(
        self,
        params: ControlHaberesFullFilter,
        siif: list[dict] = None,
        sscc: list[dict] = None,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        groupby_cols = ["ejercicio", "mes"]

        if not siif:
            siif = await self.get_siif_comprobantes_haberes_neto_rdeu(params=params)
        siif = pd.DataFrame(siif)
        if not siif.empty:
            siif = siif.loc[:, groupby_cols + ["importe"]]
            siif = siif.groupby(groupby_cols)["importe"].sum()
            siif = siif.reset_index()
            siif = siif.rename(columns={"importe": "ejecutado_siif"})
        else:
            siif = pd.DataFrame(columns=groupby_cols + ["ejecutado_siif"])
        # print(f"siif.shape: {siif.shape} - siif.head: {siif.head()}")

        if not sscc:
            sscc = await self.get_banco_invico(params=params)
        sscc = pd.DataFrame(sscc)
        if not sscc.empty:
            sscc = sscc.loc[:, groupby_cols + ["importe"]]
            sscc = sscc.groupby(groupby_cols)["importe"].sum()
            sscc = sscc.reset_index()
            sscc = sscc.rename(columns={"importe": "pagado_sscc"})
        else:
            sscc = pd.DataFrame(columns=groupby_cols + ["pagado_sscc"])
        # print(f"sscc.shape: {sscc.shape} - sscc.head: {sscc.head()}")

        df = pd.merge(siif, sscc, how="outer", on=groupby_cols, copy=False)
        df[["ejecutado_siif", "pagado_sscc"]] = df[
            ["ejecutado_siif", "pagado_sscc"]
        ].fillna(0)
        df["diferencia"] = df.ejecutado_siif - df.pagado_sscc
        df = df.sort_values(by=["ejercicio", "mes"])
        df = pd.DataFrame(df)
        df["dif_acum"] = df["diferencia"].cumsum()
        df.reset_index(drop=True, inplace=True)

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.replace({np.nan: None}).to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlHaberesLiteFilter) -> dict[str, Any]:
        """Encola la exportación a Google Sheets y responde de inmediato.

        Sube las hojas ``siif_comprobantes_haberes_db``,
        ``sscc_haberes_db`` y ``control_mensual_db``. NO se genera el
        archivo Excel (patrón ``control_viaticos``): el trabajo pesado
        corre como tarea de fondo para no bloquear el event loop ni
        agotar el timeout de Koyeb.

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
                "El Google Sheet se actualizará en segundo plano con las hojas: "
                "siif_comprobantes_haberes_db, sscc_haberes_db y "
                "control_mensual_db."
            ),
            "spreadsheet_key": SPREADSHEET_KEY_CONTROL_HABERES,
        }

    # -------------------------------------------------
    async def _export_to_google_sheets(
        self, params: ControlHaberesLiteFilter
    ) -> None:
        """Tarea de fondo: sube cada hoja a Google Sheets, una por vez.

        NO genera el archivo Excel (a diferencia del export binario
        anterior): solo queries + upload, corriendo fuera del request.
        Procesa de a una hoja para mantener el pico de memoria acotado
        (Koyeb dispone de poca RAM en su capa gratuita).

        En background no hay respuesta HTTP que retornar: los errores se
        loguean para que sean visibles en los logs de Koyeb.
        """
        search_params = ControlHaberesFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )
        async with _export_lock:
            # 1. Crudos SIIF + SSCC
            data_siif = await self.get_siif_comprobantes_haberes_neto_rdeu(
                params=search_params
            )
            data_sscc = await self.get_banco_invico(params=search_params)

            # El cruce (la tabla que ve el usuario en la página) se exporta
            # desde el snapshot persistido en Mongo; si todavía no existe,
            # se calcula on-demand para no dejar la hoja vacía.
            snapshot = await self.repository.find_with_filter_params(
                params=search_params
            )
            data_control = (
                [doc.model_dump(by_alias=True) for doc in snapshot]
                if snapshot
                else await self.compute_control_haberes(
                    params=search_params, siif=data_siif, sscc=data_sscc
                )
            )

            # 2. DataFrames + upload hoja por hoja (fuera del event loop)
            sheets: list[tuple[pd.DataFrame, str]] = [
                (pd.DataFrame(data_siif), "siif_comprobantes_haberes_db"),
                (pd.DataFrame(data_sscc), "sscc_haberes_db"),
                (pd.DataFrame(data_control), "control_mensual_db"),
            ]
            for df, sheet_name in sheets:
                try:
                    await run_in_threadpool(
                        self._build_df_and_upload, df, sheet_name
                    )
                    logger.info(
                        f"Control Haberes: hoja '{sheet_name}' "
                        "actualizada en Google Sheets"
                    )
                except Exception as e:
                    logger.error(
                        f"Control Haberes: error al subir la hoja "
                        f"'{sheet_name}': {e}"
                    )
        logger.info("Control Haberes: exportación a Google Sheets finalizada")

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
            spreadsheet_key=SPREADSHEET_KEY_CONTROL_HABERES,
        )


ControlHaberesServiceDependency = Annotated[ControlHaberesService, Depends()]
