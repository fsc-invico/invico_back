from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CargaDocument,
    CargaFullFilter,
    CargaLiteFilter,
)
from ..services import CargaService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CargaService,
    report_schema=CargaDocument,
    full_filter_schema=CargaFullFilter,  # Usa limit/offset
    lite_filter_schema=CargaLiteFilter,  # No usa limit/offset
    prefix="/carga",
)

carga_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
