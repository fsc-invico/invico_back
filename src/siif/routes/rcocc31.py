from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rcocc31Document,
    Rcocc31FullFilter,
    Rcocc31LiteFilter,
)
from ..services import Rcocc31Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rcocc31Service,
    report_schema=Rcocc31Document,
    full_filter_schema=Rcocc31FullFilter,  # Usa limit/offset
    lite_filter_schema=Rcocc31LiteFilter,  # No usa limit/offset
    prefix="/rcocc31",
)

rcocc31_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
