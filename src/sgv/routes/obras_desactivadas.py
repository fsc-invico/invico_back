from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ObrasDesactivadasDocument,
    ObrasDesactivadasFullFilter,
    ObrasDesactivadasLiteFilter,
)
from ..services import ObrasDesactivadasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ObrasDesactivadasService,
    report_schema=ObrasDesactivadasDocument,
    full_filter_schema=ObrasDesactivadasFullFilter,  # Usa limit/offset
    lite_filter_schema=ObrasDesactivadasLiteFilter,  # No usa limit/offset
    prefix="/obrasDesactivadas",
)

obras_desactivadas_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
