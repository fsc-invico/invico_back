from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rf602FullFilter,
    Rf602LiteFilter,
    Rf602Report,
)
from ..services import Rf602Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rf602Service,
    report_schema=Rf602Report,
    full_filter_schema=Rf602FullFilter,  # Usa limit/offset
    lite_filter_schema=Rf602LiteFilter,  # No usa limit/offset
    prefix="/rf602",
)

rf602_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
