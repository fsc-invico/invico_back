from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasRecuperadasDocument,
    ObrasRecuperadasFullFilter,
    ObrasRecuperadasLiteFilter,
    ObrasRecuperadasReport,
)
from ..services import ObrasRecuperadasService, ObrasRecuperadasServiceDependency

factory = GenericRouterFactory(
    service_dependency=ObrasRecuperadasService,
    report_schema=ObrasRecuperadasDocument,
    full_filter_schema=ObrasRecuperadasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasRecuperadasLiteFilter,  # No usa limit/offset
    prefix="/obrasRecuperadas",
)

obras_recuperadas_router = factory.get_router()


# -------------------------------------------------
@obras_recuperadas_router.post("/add_one")
async def add_one(
    payload: ObrasRecuperadasReport,
    service: ObrasRecuperadasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_one(obra_recuperada=payload)


# -------------------------------------------------
@obras_recuperadas_router.put(
    "/update_one/{id}", response_model=ObrasRecuperadasDocument
)
async def update_one(
    id: str,
    data: ObrasRecuperadasReport,
    service: ObrasRecuperadasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@obras_recuperadas_router.delete(
    "/delete_one/{id}", response_model=ObrasRecuperadasDocument
)
async def delete_one(
    id: str,
    service: ObrasRecuperadasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_one(id=id)
