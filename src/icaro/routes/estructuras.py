from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    EstructurasDocument,
    EstructurasFullFilter,
    EstructurasLiteFilter,
)
from ..services import EstructurasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=EstructurasService,
    report_schema=EstructurasDocument,
    full_filter_schema=EstructurasFullFilter,  # Usa limit/offset
    lite_filter_schema=EstructurasLiteFilter,  # No usa limit/offset
    prefix="/estructuras",
)

estructuras_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
