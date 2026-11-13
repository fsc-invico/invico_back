from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlViaticosFilter,
    ControlViaticosGenerateFilter,
    ControlViaticosLiteFilter,
    ControlViaticosRendicionDocument,
    ControlViaticosRendicionReport,
)
from ..services import ControlViaticosService, ControlViaticosServiceDependency

# Mono-reporte (una sola colección: control_viaticos_rendicion), por lo
# que el GenericRouterFactory cubre Get All / Add Many / Delete / Export.
# Solo queda como ruta manual el /generate on-demand.
factory = GenericRouterFactory(
    service_dependency=ControlViaticosService,
    report_schema=ControlViaticosRendicionDocument,
    full_filter_schema=ControlViaticosFilter,
    lite_filter_schema=ControlViaticosLiteFilter,
    prefix="/controlViaticos",
)

control_viaticos_router = factory.get_router()


# -------------------------------------------------
@control_viaticos_router.get(
    "/generate",
    description=(
        "Cruce Anticipo/Rendición de Viáticos calculado on-demand por el "
        "backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlViaticosRendicionReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlViaticosGenerateFilter, Depends()],
    service: ControlViaticosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)