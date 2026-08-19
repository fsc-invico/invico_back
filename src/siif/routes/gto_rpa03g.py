from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    GtoRpa03gDocument,
    GtoRpa03gFullFilter,
    GtoRpa03gLiteFilter,
)
from ..services import (  # La clase del servicio
    GtoRpa03gService,
    GtoRpa03gServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=GtoRpa03gService,
    report_schema=GtoRpa03gDocument,
    full_filter_schema=GtoRpa03gFullFilter,  # Usa limit/offset
    lite_filter_schema=GtoRpa03gLiteFilter,  # No usa limit/offset
    prefix="/gtoRpa03g",
)

rpa03g_router = factory.get_router()


# -------------------------------------------------
@rpa03g_router.get("/joinedWithRcg01Uejp")
async def get_joined_with_rcg01_uejp(
    params: Annotated[GtoRpa03gFullFilter, Depends()],
    service: GtoRpa03gServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_joined_with_rcg01_uejp(params=params)
