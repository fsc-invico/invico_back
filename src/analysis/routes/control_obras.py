from typing import List

from ...auth.services import AuthorizationDependency
from ...utils import RouteReturnSchema
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlObrasDocument,
    ControlObrasFullFilter,
    ControlObrasLiteFilter,
)
from ..services import ControlObrasService, ControlObrasServiceDependency

factory = GenericRouterFactory(
    service_dependency=ControlObrasService,
    report_schema=ControlObrasDocument,
    full_filter_schema=ControlObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlObrasLiteFilter,  # No usa limit/offset
    prefix="/controlObras",
)

control_obras_router = factory.get_router()


# -------------------------------------------------
@control_obras_router.post(
    "/compute",
    description="Compute control obras",
    response_model=List[RouteReturnSchema],
)
async def compute(
    ejercicios: List[int],
    service: ControlObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_obras(ejercicios=ejercicios)
