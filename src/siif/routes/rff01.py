from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rff01Document,
    Rff01FullFilter,
    Rff01LiteFilter,
)
from ..services import Rff01Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rff01Service,
    report_schema=Rff01Document,
    full_filter_schema=Rff01FullFilter,  # Usa limit/offset
    lite_filter_schema=Rff01LiteFilter,  # No usa limit/offset
    prefix="/rff01",
)

rff01_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
