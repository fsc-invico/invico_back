from typing import Annotated

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ResumenRendProvDocument,
    ResumenRendProvFullFilter,
    ResumenRendProvLiteFilter,
)
from ..services import (
    ResumenRendProvService,
    ResumenRendProvServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ResumenRendProvService,
    report_schema=ResumenRendProvDocument,
    full_filter_schema=ResumenRendProvFullFilter,  # Usa limit/offset
    lite_filter_schema=ResumenRendProvLiteFilter,  # No usa limit/offset
    prefix="/resumenRendProv",
)


resumen_rend_prov_router = factory.get_router()


# -------------------------------------------------
@resumen_rend_prov_router.get(
    "/dropDuplicates",
    description="Get All without duplicates",
)
async def drop_duplicates(
    params: Annotated[ResumenRendProvFullFilter, Depends()],
    service: ResumenRendProvServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.drop_duplicates(params=params)
