from ...auth.services import AuthorizationDependency
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
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_one(obra=payload)


# -------------------------------------------------
@obras_router.put("/update_one/{id}", response_model=ObrasDocument)
async def update_one(
    id: str,
    data: ObrasReport,
    service: ObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@obras_router.delete("/delete_one/{id}", response_model=ObrasDocument)
async def delete_one(
    id: str, service: ObrasServiceDependency, security: AuthorizationDependency
):
    security.is_admin_or_user_or_raise()
    return await service.delete_one(id=id)
