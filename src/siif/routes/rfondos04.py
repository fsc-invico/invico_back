from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rfondos04Document,
    Rfondos04FullFilter,
    Rfondos04LiteFilter,
)
from ..services import Rfondos04Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rfondos04Service,
    report_schema=Rfondos04Document,
    full_filter_schema=Rfondos04FullFilter,  # Usa limit/offset
    lite_filter_schema=Rfondos04LiteFilter,  # No usa limit/offset
    prefix="/rfondos04",
)

rfondos04_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
