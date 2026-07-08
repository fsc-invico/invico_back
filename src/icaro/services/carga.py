__all__ = ["CargaService", "CargaServiceDependency"]

# import os
from dataclasses import dataclass
from datetime import datetime, timezone

# from io import BytesIO
from typing import Annotated, List

import pandas as pd
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.responses import StreamingResponse

# from pydantic import ValidationError
from ...config import logger
from ...siif.repositories import Rdeu012RepositoryDependency
from ...siif.schemas import Rf602FullFilter
from ...siif.services import Rf610ServiceDependency
from ...utils import (
    BaseService,
    RouteReturnSchema,
    sanitize_dataframe_for_json_with_datetime,
    sync_validated_to_repository,
    validate_and_extract_data_from_list,
)
from ..repositories import CargaRepositoryDependency, ProveedoresRepositoryDependency
from ..schemas import (
    CargaDocument,
    CargaFullDescSIIF,
    CargaFullFilter,
    CargaLiteFilter,
    CargaReport,
    CargaWithDescProveedor,
)


@dataclass
# -------------------------------------------------
class CargaService(
    BaseService[CargaReport, CargaDocument, CargaFullFilter, CargaLiteFilter]
):
    repository: CargaRepositoryDependency
    rdeu_repo: Rdeu012RepositoryDependency
    proveedores_repo: ProveedoresRepositoryDependency
    rf610_service: Rf610ServiceDependency

    def __post_init__(self):
        # Como usamos @dataclass, el __init__ se genera solo.
        # Usamos __post_init__ para pasarle los datos a la clase base.
        self.repository.unique_field = (
            "id_carga"  # Asegúrate de que tu repositorio sepa cuál es el campo único
        )
        super().__init__(
            repository=self.repository,
            filter_schema=CargaFullFilter,  # <--- LE DECIMOS QUIÉN ES 'F'
        )

    # -------------------------------------------------
    async def add_one(self, data: CargaReport) -> CargaDocument:
        """
        Inserta un único registro verificando que el id_carga no exista.
        """
        try:
            # 1. Verificar si ya existe un registro con ese id_carga
            # Usamos el repositorio para buscar por el campo único
            new_timestamp = datetime.now(timezone.utc)
            data.updated_at = new_timestamp
            return await self.repository.save_one(data)

        except Exception as e:
            logger.error(f"Error en add_one: {str(e)}")
            self._handle_error("Error durante el proceso de add_one", e)

    # -------------------------------------------------
    async def update_one_safely(self, id: str, data: CargaReport) -> CargaDocument:
        try:
            mongo_id = ObjectId(id)
            new_timestamp = datetime.now(timezone.utc)

            # 1. VERIFICACIÓN DE ID_CARGA DUPLICADO
            # Buscamos si existe otro documento con ese id_carga que NO sea el nuestro
            duplicate = await self.repository.get_one_by_fields(
                {"id_carga": data.id_carga, "_id": {"$ne": mongo_id}}
            )

            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No se puede actualizar: El ID de Carga '{data.id_carga}' ya está siendo usado por otro comprobante.",
                )

            # 2. INTENTO DE ACTUALIZACIÓN (Control de Concurrencia)
            new_data = data.model_dump(by_alias=True)
            new_data["updated_at"] = new_timestamp

            updated_doc = await self.repository.find_one_and_update(
                filter={
                    "_id": mongo_id,
                    "updated_at": data.updated_at,  # El cerrojo
                },
                update_data=new_data,
                return_document=True,
            )

            if not updated_doc:
                # Si llegamos acá es porque el ID no existe o el updated_at cambió (Conflicto)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Conflicto de edición: Los datos fueron modificados por otro usuario. Por favor, recargue la página.",
                )

            return updated_doc
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en update_one_safely: {str(e)}")
            self._handle_error("Error durante el proceso de update_one_safely", e)

    # -------------------------------------------------
    async def delete_one(self, id: str) -> CargaDocument:
        try:
            mongo_id = ObjectId(id)
            document = await self.repository.delete_by_id(mongo_id)

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El comprobante no existe o ya fue eliminado.",
                )
            return document
        except HTTPException:
            raise  # Re-lanzamos la excepción de FastAPI si ya la manejamos
        except Exception as e:
            logger.error(f"Error en delete_one_hard: {str(e)}")
            self._handle_error("Error durante el proceso de delete_one_hard", e)

    # -------------------------------------------------
    async def add_many(self, data: List[CargaReport]) -> RouteReturnSchema:
        try:
            # 1. Validar usando tu función genérica
            validation_result = validate_and_extract_data_from_list(
                data_list=data,
                model=CargaReport,
                field_id="id_carga",  # O el campo que identifique la fila en caso de error
            )

            # 2. Determinar filtro de borrado (Idempotencia)
            # Si hay registros válidos, extraemos el ejercicio para limpiar antes de insertar
            delete_filter = {}
            # if validation_result.validated:
            #     # Tomamos el ejercicio del primer registro válido
            #     ejercicio_detectado = validation_result.validated[0].ejercicio
            #     delete_filter = {"ejercicio": ejercicio_detectado}

            # 3. Sincronizar con el repositorio usando tu función genérica
            return await sync_validated_to_repository(
                repository=self.repository,
                validation=validation_result,
                delete_filter=delete_filter,
                title="Sincronización ICARO CARGA",
                label="CARGA",
                logger=logger,  # Asegúrate de tener el logger importado
            )

        except Exception as e:
            self._handle_error("Error durante el proceso de add_many", e)

    # -------------------------------------------------
    async def export(self, params: CargaLiteFilter) -> StreamingResponse:
        # 1. Creamos el objeto de filtros normal
        search_params = CargaFullFilter(
            query_filter=params.query_filter,
            ejercicio=params.ejercicio,
            limit=None,  # Para traer todo
        )

        # 2. Traemos los datos sin paginar
        data = await self.repository.find_with_filter_params(params=search_params)

        # 3. Usar el método de la clase base
        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])
        return self.export_to_excel(
            data_pairs=[(df, "ICARO_CARGA")], filename="reporte_icaro_carga.xlsx"
        )

    # -------------------------------------------------
    async def neto_rdeu(self, params: CargaFullFilter) -> List[dict]:

        icaro_docs = await self.repository.find_with_filter_params(params=params)

        # 🔥 LA VALIDACIÓN: Si no viene nada de la base de datos, cortamos acá
        if not icaro_docs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros en ICARO's Carga para el ejercicio o filtros seleccionados.",
            )

        # Si hay datos, el flujo continúa normalmente...
        icaro = pd.DataFrame(
            [d.model_dump(by_alias=True, mode="json") for d in icaro_docs]
        )

        rdeu_docs = await self.rdeu_repo.get_all()

        # 🔥 LA VALIDACIÓN: Si no viene nada de la base de datos, simplementete devolvemos ICARO
        if not rdeu_docs:
            df = icaro

        else:
            # Si hay datos, el flujo continúa normalmente...
            rdeu = pd.DataFrame(rdeu_docs)

            # Incorporamos, con signo negativo, los registros de CARGA Icaro que hayan quedado en la deuda flotante (RDEU)
            icaro_cyo = icaro.loc[~icaro["tipo"].isin(["PA6", "REG"])]
            rdeu_deuda = rdeu.loc[:, ["nro_comprobante", "saldo", "mes"]]
            rdeu_deuda = rdeu_deuda.drop_duplicates(subset=["nro_comprobante", "mes"])
            rdeu_deuda = pd.merge(rdeu_deuda, icaro_cyo, how="inner", copy=False)
            rdeu_deuda["importe"] = rdeu_deuda.saldo * (-1)
            rdeu_deuda["tipo"] = "RDEU"
            rdeu_deuda = rdeu_deuda.drop(columns=["saldo"])
            rdeu_deuda = pd.concat([rdeu_deuda, icaro_cyo], copy=False)
            icaro_pa6 = icaro = icaro.loc[icaro["tipo"].isin(["PA6"])]
            rdeu_deuda = pd.concat([rdeu_deuda, icaro_pa6], copy=False)
            icaro_carga_neto_rdeu = rdeu_deuda

            # Ajustamos la Deuda Flotante Pagada
            rdeu = pd.DataFrame(rdeu_docs)
            rdeu = rdeu.drop_duplicates(subset=["nro_comprobante"], keep="last")
            rdeu["fecha_hasta"] = rdeu["fecha_hasta"] + pd.tseries.offsets.DateOffset(
                months=1
            )
            rdeu["mes_hasta"] = rdeu["fecha_hasta"].dt.strftime("%m/%Y")
            rdeu["ejercicio"] = pd.to_numeric(rdeu["mes_hasta"].str[-4:])

            # Incorporamos los comprobantes de gastos pagados
            # en periodos posteriores (Deuda Flotante)
            # if ejercicio is not None:
            #     if isinstance(ejercicio, list):
            #         rdeu = rdeu.loc[rdeu["ejercicio"].isin(ejercicio)]
            #     else:
            #         rdeu = rdeu.loc[rdeu["ejercicio"].isin([ejercicio])]
            rdeu = rdeu.loc[rdeu["ejercicio"] == int(params.ejercicio)]

            icaro = icaro.loc[~icaro["tipo"].isin(["PA6", "REG"])]
            icaro = icaro.loc[
                :,
                [
                    "nro_comprobante",
                    "actividad",
                    "partida",
                    "fondo_reparo",
                    "nro_certificado",
                    "avance",
                    "origen",
                    "desc_obra",
                ],
            ]
            rdeu = pd.merge(rdeu, icaro, on="nro_comprobante", copy=False)
            rdeu["importe"] = rdeu.saldo
            rdeu["tipo"] = "RDEU"
            rdeu["id_carga"] = rdeu["nro_comprobante"] + "C"
            rdeu = rdeu.loc[~rdeu["actividad"].isna()]
            rdeu = rdeu.drop(columns=["fecha", "mes"])
            rdeu = rdeu.rename(columns={"fecha_hasta": "fecha", "mes_hasta": "mes"})
            rdeu = rdeu.loc[
                :,
                [
                    "ejercicio",
                    "nro_comprobante",
                    "fuente",
                    "cuit",
                    "cta_cte",
                    "tipo",
                    "importe",
                    "id_carga",
                    "actividad",
                    "partida",
                    "fondo_reparo",
                    "nro_certificado",
                    "avance",
                    "origen",
                    "desc_obra",
                    "fecha",
                    "mes",
                ],
            ]
            df = pd.concat([rdeu, icaro_carga_neto_rdeu], copy=False)

        df = sanitize_dataframe_for_json_with_datetime(df)

        return df.to_dict(orient="records")

    # -------------------------------------------------
    async def with_desc_proveedores(
        self, params: CargaFullFilter
    ) -> List[CargaWithDescProveedor]:
        data = await self.repository.find_with_filter_params(params=params)

        # 🔥 LA VALIDACIÓN: Si no viene nada de la base de datos, cortamos acá
        if not data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontraron registros de Carga en Icaro para los filtros seleccionados.",
            )

        df = pd.DataFrame([d.model_dump(by_alias=True, mode="json") for d in data])

        proveedores_docs = await self.proveedores_repo.get_all()

        # 🔥 LA VALIDACIÓN: Si no viene nada de la base de datos, simplementete devolvemos ICARO
        if not proveedores_docs:
            df["desc_proveedor"] = None
        else:
            prov = pd.DataFrame(proveedores_docs)
            prov = prov.loc[:, ["cuit", "desc_proveedor"]]
            prov.drop_duplicates(subset=["cuit"], inplace=True)
            # prov.rename(columns={"desc_proveedor": "proveedor"}, inplace=True)
            df = df.merge(prov, how="left", on="cuit", copy=False)

        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data

    # -------------------------------------------------
    async def full_desc_siif(self, params: CargaFullFilter) -> List[CargaFullDescSIIF]:

        df = pd.DataFrame(await self.with_desc_proveedores(params=params))

        search_params = Rf602FullFilter(
            query_filter=f"ejercicio<={int(df['ejercicio'].max())}",
            ejercicio=None,
            limit=None,  # Para traer todo
        )

        df_siif = pd.DataFrame(
            await self.rf610_service.desc_estructuras(params=search_params)
        )

        df["estructura"] = df["actividad"] + "-" + df["partida"]
        df = df.merge(
            df_siif,
            how="left",
            on="estructura",
            copy=False,
        )
        df.drop(labels=["estructura"], axis="columns", inplace=True)

        df = sanitize_dataframe_for_json_with_datetime(df)
        json_data = df.to_dict(orient="records")
        return json_data


CargaServiceDependency = Annotated[CargaService, Depends()]
