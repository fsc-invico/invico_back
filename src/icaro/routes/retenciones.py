from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    RetencionesBatchCreate,
    RetencionesDocument,
    RetencionesFullFilter,
    RetencionesLiteFilter,
)
from ..services import RetencionesService, RetencionesServiceDependency

factory = GenericRouterFactory(
    service_dependency=RetencionesService,
    report_schema=RetencionesDocument,
    full_filter_schema=RetencionesFullFilter,  # Usa limit/offset
    lite_filter_schema=RetencionesLiteFilter,  # No usa limit/offset
    prefix="/retenciones",
)

retenciones_router = factory.get_router()


# -------------------------------------------------
@retenciones_router.delete("/delete_many/{id_carga:path}")
async def delete_many_by_carga_id(id_carga: str, service: RetencionesServiceDependency):
    return await service.delete_many_by_carga_id(id_carga=id_carga)


# -------------------------------------------------
@retenciones_router.post("/add_many/{id_carga:path}")
async def add_many_retenciones(
    id_carga: str,
    payload: RetencionesBatchCreate,
    service: RetencionesServiceDependency,
):
    return await service.add_many_with_id_carga(
        id_carga=id_carga, items=payload.retenciones
    )
