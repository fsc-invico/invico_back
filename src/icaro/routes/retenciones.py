from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    RetencionesDocument,
    RetencionesFullFilter,
    RetencionesLiteFilter,
)
from ..services import RetencionesService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=RetencionesService,
    report_schema=RetencionesDocument,
    full_filter_schema=RetencionesFullFilter,  # Usa limit/offset
    lite_filter_schema=RetencionesLiteFilter,  # No usa limit/offset
    prefix="/retenciones",
)

retenciones_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
