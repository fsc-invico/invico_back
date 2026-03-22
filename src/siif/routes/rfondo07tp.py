from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rfondo07tpDocument,
    Rfondo07tpFullFilter,
    Rfondo07tpLiteFilter,
)
from ..services import Rfondo07tpService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rfondo07tpService,
    report_schema=Rfondo07tpDocument,
    full_filter_schema=Rfondo07tpFullFilter,  # Usa limit/offset
    lite_filter_schema=Rfondo07tpLiteFilter,  # No usa limit/offset
    prefix="/rfondo07tp",
)

rfondo07tp_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
