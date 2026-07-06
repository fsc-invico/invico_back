from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rf610DescEstructuras,
    Rf610Document,
    Rf610FullFilter,
    Rf610LiteFilter,
)
from ..services import Rf610Service, Rf610ServiceDependency

factory = GenericRouterFactory(
    service_dependency=Rf610Service,
    report_schema=Rf610Document,
    full_filter_schema=Rf610FullFilter,  # Usa limit/offset
    lite_filter_schema=Rf610LiteFilter,  # No usa limit/offset
    prefix="/rf610",
)

rf610_router = factory.get_router()


# -------------------------------------------------
@rf610_router.get(
    "/descEstructuras",
    description="Get All Estructuras with Descriptions",
    response_model=list[Rf610DescEstructuras],
)
async def desc_estructuras(
    params: Annotated[Rf610FullFilter, Depends()],
    service: Rf610ServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.desc_estructuras(params=params)
