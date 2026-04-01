from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasDocument,
    ObrasFullFilter,
    ObrasLiteFilter,
)
from ..services import ObrasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ObrasService,
    report_schema=ObrasDocument,
    full_filter_schema=ObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasLiteFilter,  # No usa limit/offset
    prefix="/obras",
)

obras_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
