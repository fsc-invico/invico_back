from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rpa03gDocument,
    Rpa03gFullFilter,
    Rpa03gLiteFilter,
)
from ..services import Rpa03gService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rpa03gService,
    report_schema=Rpa03gDocument,
    full_filter_schema=Rpa03gFullFilter,  # Usa limit/offset
    lite_filter_schema=Rpa03gLiteFilter,  # No usa limit/offset
    prefix="/gtoRpa03g",
)

rpa03g_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
