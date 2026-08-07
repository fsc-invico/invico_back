from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rci02Document,
    Rci02FullFilter,
    Rci02LiteFilter,
    Rci02SummarizedReport,
)
from ..services import Rci02Service, Rci02ServiceDependency  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rci02Service,
    report_schema=Rci02Document,
    full_filter_schema=Rci02FullFilter,  # Usa limit/offset
    lite_filter_schema=Rci02LiteFilter,  # No usa limit/offset
    prefix="/rci02",
)

rci02_router = factory.get_router()


# -------------------------------------------------
@rci02_router.get(
    "/summarize",
    description="Get grouped Rci02 data",
    response_model=list[Rci02SummarizedReport],
    response_model_exclude_none=True,
)
async def summarize(
    params: Annotated[Rci02FullFilter, Depends()],
    service: Rci02ServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.summarize(params=params)
