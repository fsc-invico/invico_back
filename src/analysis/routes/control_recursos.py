from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlRecursosFullFilter,
    ControlRecursosLiteFilter,
    ControlRecursosReport,
)
from ..services import ControlRecursosService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ControlRecursosService,
    report_schema=ControlRecursosReport,
    full_filter_schema=ControlRecursosFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlRecursosLiteFilter,  # No usa limit/offset
    prefix="/controlRecursos",
)

control_recursos_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# control_recursos_router = factory.get_router()


# @control_recursos_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
