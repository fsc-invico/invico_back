__all__ = [
    "ControlHaberesService",
    "ControlHaberesServiceDependency",
]

from dataclasses import dataclass
from typing import Annotated

import numpy as np
import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

from ...siif.schemas import GtoRpa03gFullFilter, Rcocc31FullFilter, Rdeu012FullFilter
from ...siif.services import (
    GtoRpa03gServiceDependency,
    Rcocc31ServiceDependency,
    Rdeu012ServiceDependency,
)
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
    contabilidad_service: Rcocc31ServiceDependency
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
                ].drop_duplicates(subset=["nro_comprobante"], keep="first"),
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
