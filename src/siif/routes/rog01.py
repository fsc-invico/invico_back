from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rog01Document,
    Rog01FullFilter,
    Rog01LiteFilter,
)
from ..services import Rog01Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rog01Service,
    report_schema=Rog01Document,
    full_filter_schema=Rog01FullFilter,  # Usa limit/offset
    lite_filter_schema=Rog01LiteFilter,  # No usa limit/offset
    prefix="/rog01",
)

rog01_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
