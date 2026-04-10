from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ResumenRendObrasDocument,
    ResumenRendObrasFullFilter,
    ResumenRendObrasLiteFilter,
)
from ..services import ResumenRendObrasService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ResumenRendObrasService,
    report_schema=ResumenRendObrasDocument,
    full_filter_schema=ResumenRendObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ResumenRendObrasLiteFilter,  # No usa limit/offset
    prefix="/resumenRendObras",
)

resumen_rend_obras_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
