__all__ = ["ResumenRendProvService", "ResumenRendProvServiceDependency"]

# import os
from dataclasses import dataclass

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from fastapi import Depends
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import ResumenRendProvRepositoryDependency
from ..schemas import (
    ResumenRendProvDocument,
    ResumenRendProvFullFilter,
    ResumenRendProvLiteFilter,
    ResumenRendProvReport,
)


@dataclass
# -------------------------------------------------
class ResumenRendProvService(
    BaseService[
        ResumenRendProvReport,
        ResumenRendProvDocument,
        ResumenRendProvFullFilter,
        ResumenRendProvLiteFilter,
    ]
):
    repository: ResumenRendProvRepositoryDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        super().__init__(
            repository=self.repository,
            filter_schema=ResumenRendProvFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_many(self, data: List[ResumenRendProvReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=ResumenRendProvReport,
                field_id=[
                    "origen",
                    "libramiento",
                ],  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            if validation_result.validated:
                # Tomamos el ejercicio del primer registro válido
                ejercicio_detectado = validation_result.validated[0].ejercicio
                origen_detectado = validation_result.validated[0].origen
                delete_filter = {
                    "ejercicio": ejercicio_detectado,
                    "origen": origen_detectado,
                }

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización SGF Resumen Rend Prov",
                label="Resumen Rend Prov",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: ResumenRendProvLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = ResumenRendProvFullFilter(
            query_filter=params.query_filter,
            origen=params.origen,
            ejercicio=params.ejercicio,
            # beneficiario=params.beneficiario,
            # cta_cte=params.cta_cte,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "SGF_Resumen_Rend_Prov")],
            filename="reporte_resumen_rend_prov.xlsx",
        )

    # -------------------------------------------------
    async def drop_duplicates(self, params: ResumenRendProvFullFilter):

        data = await self.repository.find_with_filter_params(params=params)

        df = pd.DataFrame([d.model_dump(by_alias=True) for d in data])

        df = df.loc[df["origen"] != "FUNCIONAMIENTO"]

        # Filtramos los registros de honorarios en EPAM
        df_epam = df.copy()
        keep = ["HONORARIOS"]
        df_epam = df_epam.loc[df_epam["origen"] == "EPAM"]
        df_epam = df_epam.loc[~df_epam.destino.str.contains("|".join(keep))]
        df = df.loc[df["origen"] != "EPAM"]
        df = pd.DataFrame(pd.concat([df, df_epam], ignore_index=True))

        # Filtramos los registros duplicados en la 106
        df_106 = df.copy()
        df_106 = df_106.loc[df_106["cta_cte"] == "106"]
        df_106 = df_106.drop_duplicates(
            subset=["mes", "fecha", "beneficiario", "libramiento", "importe_bruto"]
        )
        df = pd.concat([df[df["cta_cte"] != "106"], df_106], ignore_index=True)

        # Filtramos los registros duplicados en la 07
        df_07 = df.copy()
        df_07 = df_07.loc[df_07["cta_cte"] == "130832-07"]
        df_07 = df_07.sort_values(["libramiento", "destino"], ascending=False)
        df_07 = df_07.drop_duplicates(
            subset=[
                "mes",
                "fecha",
                "beneficiario",
                "libramiento",
                "importe_bruto",
                "gcias",
                "sellos",
                "iibb",
                "suss",
                "invico",
                "seguro",
                "salud",
                "mutual",
                "otras",
                "retenciones",
                "importe_neto",
            ]
        )
        df = pd.concat([df[df["cta_cte"] != "130832-07"], df_07], ignore_index=True)

        # Filtramos los registros duplicados en la 03
        df_03 = df.copy()
        df_03 = df_03.loc[df_03["cta_cte"] == "130832-03"]
        df_03 = df_03.sort_values(["libramiento", "destino"], ascending=False)
        df_03 = df_03.drop_duplicates(
            subset=[
                "mes",
                "fecha",
                "beneficiario",
                "libramiento",
                "importe_bruto",
                "gcias",
                "sellos",
                "iibb",
                "suss",
                "invico",
                "seguro",
                "salud",
                "mutual",
                "otras",
                "retenciones",
                "importe_neto",
            ]
        )
        df = pd.concat([df[df["cta_cte"] != "130832-03"], df_03], ignore_index=True)

        # Filtramos los registros duplicados en la 03
        df_13 = df.copy()
        df_13 = df_13.loc[df_13["cta_cte"] == "130832-13"]
        df_13 = df_13.sort_values(["libramiento", "destino"], ascending=False)
        df_13 = df_13.drop_duplicates(
            subset=[
                "mes",
                "fecha",
                "beneficiario",
                "libramiento",
                "importe_bruto",
                "gcias",
                "sellos",
                "iibb",
                "suss",
                "invico",
                "seguro",
                "salud",
                "mutual",
                "otras",
                "retenciones",
                "importe_neto",
            ]
        )
        df = pd.concat([df[df["cta_cte"] != "130832-13"], df_13], ignore_index=True)

        # Filtramos los registros duplicados en la 221078150
        df_2210178150 = df.copy()
        df_2210178150 = df_2210178150.loc[df_2210178150["cta_cte"] == "2210178150"]
        df_2210178150 = df_2210178150.drop_duplicates(
            subset=["mes", "fecha", "beneficiario", "libramiento", "importe_bruto"]
        )
        # df = df[df["cta_cte"] != "2210178150"]
        df = pd.concat(
            [df[df["cta_cte"] != "2210178150"], df_2210178150], ignore_index=True
        )

        df = sanitize_dataframe_for_json_with_datetime(df)
        df = df.head(100)

        return df.to_dict(orient="records")


ResumenRendProvServiceDependency = Annotated[ResumenRendProvService, Depends()]
