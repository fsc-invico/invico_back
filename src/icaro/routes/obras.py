from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasDocument,
    ObrasFullFilter,
    ObrasLiteFilter,
    ObrasReport,
)
from ..services import ObrasService, ObrasServiceDependency

factory = GenericRouterFactory(
    service_dependency=ObrasService,
    report_schema=ObrasDocument,
    full_filter_schema=ObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasLiteFilter,  # No usa limit/offset
    prefix="/obras",
)

obras_router = factory.get_router()


# -------------------------------------------------
@obras_router.post("/add_one")
async def add_one_obra(
    payload: ObrasReport,
    service: ObrasServiceDependency,
):
    return await service.add_one(obra=payload)
