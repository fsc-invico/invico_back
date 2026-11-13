from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlDebitosBancariosFilter,
    ControlDebitosBancariosGenerateFilter,
    ControlDebitosBancariosLiteFilter,
    ControlDebitosBancariosDocument,
    ControlDebitosBancariosReport,
)
from ..services import (
    ControlDebitosBancariosService,
    ControlDebitosBancariosServiceDependency,
)

# Mono-reporte (una sola colección: control_debitos_bancarios), por lo
# que el GenericRouterFactory cubre Get All / Add Many / Delete / Export
# (el export responde JSON y sube a Google Sheet en background vía
# asyncio.create_task, sin generar el XLS). Solo queda como ruta manual
# el /generate on-demand.
factory = GenericRouterFactory(
    service_dependency=ControlDebitosBancariosService,
    report_schema=ControlDebitosBancariosDocument,
    full_filter_schema=ControlDebitosBancariosFilter,
    lite_filter_schema=ControlDebitosBancariosLiteFilter,
    prefix="/controlDebitosBancarios",
)

control_debitos_bancarios_router = factory.get_router()


# -------------------------------------------------
@control_debitos_bancarios_router.get(
    "/generate",
    description=(
        "Cruce Débitos Bancarios SIIF vs SSCC calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlDebitosBancariosReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlDebitosBancariosGenerateFilter, Depends()],
    service: ControlDebitosBancariosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)