from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rci02Document,
    Rci02FullFilter,
    Rci02LiteFilter,
)
from ..services import Rci02Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rci02Service,
    report_schema=Rci02Document,
    full_filter_schema=Rci02FullFilter,  # Usa limit/offset
    lite_filter_schema=Rci02LiteFilter,  # No usa limit/offset
    prefix="/rci02",
)

rci02_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
