__all__ = [
    "ControlHaberesService",
    "ControlHaberesServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.schemas import GtoRpa03gFullFilter, Rdeu012FullFilter
from ...siif.services import GtoRpa03gServiceDependency, Rdeu012ServiceDependency
from ...sscc.services import CtasCtesServiceDependency
from ...utils import (
    export_multiple_dataframes_to_excel,
    sanitize_dataframe_for_json_with_datetime,
)
from ..schemas import (
    ControlHaberesFilter,
    ControlHaberesLiteFilter,
)


@dataclass
# -------------------------------------------------
class ControlHaberesService:
    gastos_service: GtoRpa03gServiceDependency
    rdeu_service: Rdeu012ServiceDependency
    cta_cte_service: CtasCtesServiceDependency

    # -------------------------------------------------
    async def get_siif_comprobantes_haberes_neto_rdeu(
        self,
        params: ControlHaberesFilter,
    ) -> list[dict]:
        if params.ejercicio is None:
            raise ValueError("El parámetro 'ejercicio' es obligatorio.")

        gastos_params = GtoRpa03gFullFilter(
            ejercicio=str(params.ejercicio),
            limit=params.limit,
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

        # 4. Traemos la deuda flotante filtrada
        rdeu_params = Rdeu012FullFilter(
            query_filter="cta_cte=130832-04",
            limit=params.limit,
        )
        # Obtenemos los meses a descargar
        meses = [f"12/{str(params.ejercicio - 1)}"]
        for mes in range(1, 13):
            periodo_str = f"{mes:02d}/{str(params.ejercicio)}"
            meses.append(periodo_str)

        rdeu_params.set_extra_filter({"mes_hasta": {"$in": meses}})

        # comprobantes_unicos = df["nro_comprobante"].unique().tolist()
        # print(comprobantes_unicos)
        # rdeu_params.set_extra_filter({"nro_comprobante": {"$in": comprobantes_unicos}})

        data_rdeu = await self.rdeu_service.get_all(params=rdeu_params)
        if data_rdeu:
            rdeu = pd.DataFrame([d.model_dump(by_alias=True) for d in data_rdeu])
            rdeu = rdeu.drop(
                columns=["id"], errors="ignore"
            )  # Eliminar la columna 'id' si existe
            # Detectamos los comprobantes que quedaron impagos y le cambiamos el signo
            registros_impagos = df.loc[
                df["nro_comprobante"].isin(rdeu["nro_comprobante"].unique().tolist())
            ].copy()
            registros_impagos["importe"] = registros_impagos["importe"] * (-1)
            df = pd.concat([df, registros_impagos], copy=False)
            # Ajustamos la Deuda Flotante Pagada
            rdeu = rdeu.drop_duplicates(subset=["nro_comprobante"], keep="last")
            rdeu["fecha_hasta"] = rdeu["fecha_hasta"] + pd.tseries.offsets.DateOffset(
                months=1
            )
            rdeu["mes_hasta"] = rdeu["fecha_hasta"].dt.strftime("%m/%Y")
            rdeu["ejercicio"] = pd.to_numeric(rdeu["mes_hasta"].str[-4:])
            rdeu = rdeu.loc[rdeu["ejercicio"] == int(params.ejercicio)]
            rdeu = pd.merge(
                rdeu,
                df.loc[
                    :,
                    [
                        "nro_comprobante",
                        "grupo",
                        "partida",
                        "nro_fondo",
                        "clase_reg",
                        "clase_mod",
                        "clase_gto",
                        "es_comprometido",
                        "es_verificado",
                        "es_aprobado",
                        "es_pagado",
                    ],
                ],
                on="nro_comprobante",
                copy=False,
            )
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
            df = pd.concat([df, rdeu], copy=False)

        # 4. Sanitización final
        df = sanitize_dataframe_for_json_with_datetime(df)
        print(df.head())

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def export(self, params: ControlHaberesLiteFilter) -> StreamingResponse:

        # 1. Creamos el objeto de filtros normal
        params = ControlHaberesFilter(
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data_haberes = await self.get_siif_comprobantes_haberes_neto_rdeu(params=params)
        # data_retenciones_siif = await self.get_retenciones_from_siif(params=params)
        # data_retenciones_icaro = await self.get_retenciones_from_icaro(params=params)
        # data_control_siif = await self.generate_siif(params=params)
        # data_control_icaro = await self.generate_icaro(params=params)

        # 3. Transformamos los datos a DataFrames de Pandas
        df_haberes = pd.DataFrame(data_haberes)

        # df_retenciones_siif = pd.DataFrame(data_retenciones_siif)

        # df_retenciones_icaro = pd.DataFrame(data_retenciones_icaro)

        # df_control_siif = pd.DataFrame(data_control_siif)

        # df_control_icaro = pd.DataFrame(data_control_icaro)

        return export_multiple_dataframes_to_excel(
            data_pairs=[
                (df_haberes, "siif_comprobantes_haberes_db"),
                # (df_retenciones_siif, "retenciones_siif_db"),
                # (df_retenciones_icaro, "retenciones_icaro_db"),
                # (df_control_siif, "control_cruzado_siif_db"),
                # (df_control_icaro, "control_cruzado_icaro_db"),
            ],
            filename="Control Haberes.xlsx",
            upload_to_google_sheets=True,
            spreadsheet_key="1A9ypUkwm4kfLqUAwr6-55crcFElisOO9fOdI6iflMAc",
        )


ControlHaberesServiceDependency = Annotated[ControlHaberesService, Depends()]
