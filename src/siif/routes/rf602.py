from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rf602Document,
    Rf602FullFilter,
    Rf602LiteFilter,
    Rf602WithDescEstructuras,
)
from ..services import Rf602Service, Rf602ServiceDependency

factory = GenericRouterFactory(
    service_dependency=Rf602Service,
    report_schema=Rf602Document,
    full_filter_schema=Rf602FullFilter,  # Usa limit/offset
    lite_filter_schema=Rf602LiteFilter,  # No usa limit/offset
    prefix="/rf602",
)

rf602_router = factory.get_router()


# -------------------------------------------------
@rf602_router.get(
    "/withDescEstructuras",
    description="Get rf602 with Descriptions of Estructuras",
    response_model=list[Rf602WithDescEstructuras],
)
async def desc_estructuras(
    params: Annotated[Rf602FullFilter, Depends()],
    service: Rf602ServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.with_desc_estructuras(params=params)
