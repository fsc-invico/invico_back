from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Ri102Document,
    Ri102FullFilter,
    Ri102LiteFilter,
)
from ..services import Ri102Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Ri102Service,
    report_schema=Ri102Document,
    full_filter_schema=Ri102FullFilter,  # Usa limit/offset
    lite_filter_schema=Ri102LiteFilter,  # No usa limit/offset
    prefix="/ri102",
)

ri102_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
