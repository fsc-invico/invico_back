from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    RfpP605bDocument,
    RfpP605bFullFilter,
    RfpP605bLiteFilter,
)
from ..services import RfpP605bService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=RfpP605bService,
    report_schema=RfpP605bDocument,
    full_filter_schema=RfpP605bFullFilter,  # Usa limit/offset
    lite_filter_schema=RfpP605bLiteFilter,  # No usa limit/offset
    prefix="/rfpP605b",
)

rfp_p605b_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
