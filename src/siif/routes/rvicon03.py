from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rvicon03Document,
    Rvicon03FullFilter,
    Rvicon03LiteFilter,
)
from ..services import Rvicon03Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rvicon03Service,
    report_schema=Rvicon03Document,
    full_filter_schema=Rvicon03FullFilter,  # Usa limit/offset
    lite_filter_schema=Rvicon03LiteFilter,  # No usa limit/offset
    prefix="/rvicon03",
)

rvicon03_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf610_router = factory.get_router()


# @rf610_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
