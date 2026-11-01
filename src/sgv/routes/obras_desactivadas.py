from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasDesactivadasDocument,
    ObrasDesactivadasFullFilter,
    ObrasDesactivadasLiteFilter,
    ObrasDesactivadasReport,
)
from ..services import ObrasDesactivadasService, ObrasDesactivadasServiceDependency

factory = GenericRouterFactory(
    service_dependency=ObrasDesactivadasService,
    report_schema=ObrasDesactivadasDocument,
    full_filter_schema=ObrasDesactivadasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasDesactivadasLiteFilter,  # No usa limit/offset
    prefix="/obrasDesactivadas",
)

obras_desactivadas_router = factory.get_router()


# -------------------------------------------------
@obras_desactivadas_router.post("/add_one")
async def add_one(
    payload: ObrasDesactivadasReport,
    service: ObrasDesactivadasServiceDependency,
    security: AuthorizationDependency,
) -> ObrasDesactivadasDocument:
    security.is_admin_or_user_or_raise()
    return await service.add_one(obra_desactivada=payload)


# -------------------------------------------------
@obras_desactivadas_router.put(
    "/update_one/{id}", response_model=ObrasDesactivadasDocument
)
async def update_one(
    id: str,
    data: ObrasDesactivadasReport,
    service: ObrasDesactivadasServiceDependency,
    security: AuthorizationDependency,
) -> ObrasDesactivadasDocument:
    security.is_admin_or_user_or_raise()
    return await service.update_one_safely(id=id, data=data)


# -------------------------------------------------
@obras_desactivadas_router.delete(
    "/delete_one/{id}", response_model=ObrasDesactivadasDocument
)
async def delete_one(
    id: str,
    service: ObrasDesactivadasServiceDependency,
    security: AuthorizationDependency,
) -> ObrasDesactivadasDocument:
    security.is_admin_or_user_or_raise()
    return await service.delete_one(id=id)


# -------------------------------------------------
@obras_desactivadas_router.get(
    "/uniqueCtaContable",
    description="Get All Cta. Contable",
    response_model=list[str],
)
async def unique_cta_contable(
    service: ObrasDesactivadasServiceDependency,
) -> list[str]:
    return await service.unique_cta_contable()
