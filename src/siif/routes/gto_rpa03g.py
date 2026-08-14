from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rpa03gDocument,
    Rpa03gFullFilter,
    Rpa03gLiteFilter,
)
from ..services import Rpa03gService, Rpa03gServiceDependency  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rpa03gService,
    report_schema=Rpa03gDocument,
    full_filter_schema=Rpa03gFullFilter,  # Usa limit/offset
    lite_filter_schema=Rpa03gLiteFilter,  # No usa limit/offset
    prefix="/gtoRpa03g",
)

rpa03g_router = factory.get_router()


# -------------------------------------------------
@rpa03g_router.get("/joinedWithRcg01Uejp")
async def get_joined_with_rcg01_uejp(
    params: Annotated[Rpa03gFullFilter, Depends()],
    service: Rpa03gServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_joined_with_rcg01_uejp(params=params)
