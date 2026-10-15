from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasRecuperadasDocument,
    ObrasRecuperadasFullFilter,
    ObrasRecuperadasLiteFilter,
)
from ..services import ObrasRecuperadasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ObrasRecuperadasService,
    report_schema=ObrasRecuperadasDocument,
    full_filter_schema=ObrasRecuperadasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasRecuperadasLiteFilter,  # No usa limit/offset
    prefix="/obrasRecuperadas",
)

obras_recuperadas_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
