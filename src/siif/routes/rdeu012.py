from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rdeu012Document,
    Rdeu012FullFilter,
    Rdeu012LiteFilter,
)
from ..services import Rdeu012Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rdeu012Service,
    report_schema=Rdeu012Document,
    full_filter_schema=Rdeu012FullFilter,  # Usa limit/offset
    lite_filter_schema=Rdeu012LiteFilter,  # No usa limit/offset
    prefix="/rdeu012",
)

rdeu012_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
