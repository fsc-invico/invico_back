from typing import List

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    HonorariosDocument,
    HonorariosFullFilter,
    HonorariosLiteFilter,
    HonorariosReport,
    HonorariosUpdate,
)
from ..services import HonorariosService, HonorariosServiceDependency

factory = GenericRouterFactory(
    service_dependency=HonorariosService,
    report_schema=HonorariosDocument,
    full_filter_schema=HonorariosFullFilter,  # Usa limit/offset
    lite_filter_schema=HonorariosLiteFilter,  # No usa limit/offset
    prefix="/honorarios",
)

honorarios_router = factory.get_router()


# -------------------------------------------------
@honorarios_router.delete("/delete_many/{nro_comprobante:path}")
async def delete_many_by_nro_comprobante(
    nro_comprobante: str,
    service: HonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_many_by_nro_comprobante(nro_comprobante=nro_comprobante)


# -------------------------------------------------
@honorarios_router.post("/add_many/{nro_comprobante:path}")
async def add_many_by_nro_comprobante(
    # Si el nro_comprobante del delete_filter (path) ya existe en la BD,
    # el servicio responde 409 para evitar duplicar el comprobante.
    nro_comprobante: str,
    payload: List[HonorariosReport],
    service: HonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many_by_nro_comprobante(
        data=payload, delete_filter={"nro_comprobante": nro_comprobante}
    )


# -------------------------------------------------
@honorarios_router.put("/update_many/{nro_comprobante:path}")
async def update_many_by_nro_comprobante(
    # nro_comprobante de la path = valor ACTUAL (filtro); el payload puede
    # traer el nuevo nro_comprobante con el que se reemplazarán los documentos.
    nro_comprobante: str,
    payload: HonorariosUpdate,
    service: HonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_many_by_nro_comprobante(
        nro_comprobante=nro_comprobante, update_data=payload
    )


# -------------------------------------------------
@honorarios_router.get("/tiposComprobantes")
async def get_tipos_comprobantes(
    service: HonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_tipos_comprobantes()


# -------------------------------------------------
@honorarios_router.get("/ctasCtes")
async def get_ctas_ctes(
    service: HonorariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_ctas_ctes()
