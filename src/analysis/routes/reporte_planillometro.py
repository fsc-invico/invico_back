from typing import Annotated

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import ReportePlanillometroFilter
from ..services import ReportePlanillometroServiceDependency

reporte_planillometro_router = APIRouter(prefix="/reportePlanillometro")


# -------------------------------------------------
@reporte_planillometro_router.post(
    "/compute",
    description="Compute control obras",
    # response_model=List[RouteReturnSchema],
)
async def compute(
    params: Annotated[ReportePlanillometroFilter, Depends()],
    service: ReportePlanillometroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_planillometro_icaro(params=params)
