from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rcg01UejpDocument,
    Rcg01UejpFullFilter,
    Rcg01UejpLiteFilter,
)
from ..services import Rcg01UejpService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rcg01UejpService,
    report_schema=Rcg01UejpDocument,
    full_filter_schema=Rcg01UejpFullFilter,  # Usa limit/offset
    lite_filter_schema=Rcg01UejpLiteFilter,  # No usa limit/offset
    prefix="/rcg01Uejp",
)

rcg01_uejp_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
