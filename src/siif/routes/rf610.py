from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    Rf610FullFilter,
    Rf610LiteFilter,
    Rf610Report,
)
from ..services import Rf610Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rf610Service,
    report_schema=Rf610Report,
    full_filter_schema=Rf610FullFilter,  # Usa limit/offset
    lite_filter_schema=Rf610LiteFilter,  # No usa limit/offset
    prefix="/rf610",
)

rf610_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf610_router = factory.get_router()


# @rf610_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
