__all__ = ["control_banco_router"]

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import ControlBancoLiteFilter
from ..services import (
    ControlBancoServiceDependency,
)

control_banco_router = APIRouter(prefix="/controlBanco")


# -------------------------------------------------
@control_banco_router.get("/export", name="Export to Google Sheets")
async def export(
    params: Annotated[ControlBancoLiteFilter, Depends()],
    service: ControlBancoServiceDependency,
    security: AuthorizationDependency,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    security.is_admin_or_user_or_raise()
    return await service.export(params=params, background_tasks=background_tasks)
