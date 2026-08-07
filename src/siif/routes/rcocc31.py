from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rcocc31Document,
    Rcocc31FullFilter,
    Rcocc31LiteFilter,
    Rcocc31SummarizedReport,
)
from ..services import Rcocc31Service, Rcocc31ServiceDependency

factory = GenericRouterFactory(
    service_dependency=Rcocc31Service,
    report_schema=Rcocc31Document,
    full_filter_schema=Rcocc31FullFilter,  # Usa limit/offset
    lite_filter_schema=Rcocc31LiteFilter,  # No usa limit/offset
    prefix="/rcocc31",
)

rcocc31_router = factory.get_router()


# -------------------------------------------------
@rcocc31_router.get(
    "/summarize",
    description="Get grouped Rcocc31 data",
    response_model=list[Rcocc31SummarizedReport],
    response_model_exclude_none=True,
)
async def summarize(
    params: Annotated[Rcocc31FullFilter, Depends()],
    service: Rcocc31ServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.summarize(params=params)
