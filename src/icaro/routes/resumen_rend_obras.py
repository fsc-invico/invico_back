from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ResumenRendObrasDocument,
    ResumenRendObrasFullFilter,
    ResumenRendObrasLiteFilter,
    ResumenRendObrasUpdateIdCarga,
)
from ..services import ResumenRendObrasService, ResumenRendObrasServiceDependency

factory = GenericRouterFactory(
    service_dependency=ResumenRendObrasService,
    report_schema=ResumenRendObrasDocument,
    full_filter_schema=ResumenRendObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ResumenRendObrasLiteFilter,  # No usa limit/offset
    prefix="/resumenRendObras",
)

resumen_rend_obras_router = factory.get_router()


# -------------------------------------------------
@resumen_rend_obras_router.patch("/update_id_carga")
async def update_id_carga(
    payload: ResumenRendObrasUpdateIdCarga,
    service: ResumenRendObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_id_carga(ids=payload.ids, id_carga=payload.id_carga)


# -------------------------------------------------
@resumen_rend_obras_router.patch("/unlink_by_carga/{id_carga:path}")
async def unlink_id_carga(
    id_carga: str,
    service: ResumenRendObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.unlink_carga_value(id_carga=id_carga)
