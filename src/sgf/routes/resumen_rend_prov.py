from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ResumenRendProvDocument,
    ResumenRendProvFullFilter,
    ResumenRendProvLiteFilter,
)
from ..services import ResumenRendProvService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ResumenRendProvService,
    report_schema=ResumenRendProvDocument,
    full_filter_schema=ResumenRendProvFullFilter,  # Usa limit/offset
    lite_filter_schema=ResumenRendProvLiteFilter,  # No usa limit/offset
    prefix="/resumenRendProv",
)

resumen_rend_prov_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
