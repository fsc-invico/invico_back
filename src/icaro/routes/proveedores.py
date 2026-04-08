from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ProveedoresDocument,
    ProveedoresFullFilter,
    ProveedoresLiteFilter,
)
from ..services import ProveedoresService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=ProveedoresService,
    report_schema=ProveedoresDocument,
    full_filter_schema=ProveedoresFullFilter,  # Usa limit/offset
    lite_filter_schema=ProveedoresLiteFilter,  # No usa limit/offset
    prefix="/proveedores",
)

proveedores_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
