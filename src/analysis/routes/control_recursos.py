from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlRecursosDocument,
    ControlRecursosFullFilter,
    ControlRecursosGenerateFilter,
    ControlRecursosLiteFilter,
    ControlRecursosReport,
)
from ..services import (  # La clase del servicio y su dependencia FastAPI
    ControlRecursosService,
    ControlRecursosServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ControlRecursosService,
    report_schema=ControlRecursosDocument,
    full_filter_schema=ControlRecursosFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlRecursosLiteFilter,  # No usa limit/offset
    prefix="/controlRecursos",
)

control_recursos_router = factory.get_router()


# -------------------------------------------------
@control_recursos_router.get(
    "/generate",
    description=(
        "Cruce SIIF rci02 vs SSCC Banco INVICO calculado on-demand "
        "por el backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlRecursosReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlRecursosGenerateFilter, Depends()],
    service: ControlRecursosServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# control_recursos_router = factory.get_router()


# @control_recursos_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
