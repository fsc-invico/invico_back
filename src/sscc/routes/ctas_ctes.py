from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CtasCtesDocument,
    CtasCtesFullFilter,
    CtasCtesLiteFilter,
)
from ..services import CtasCtesService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CtasCtesService,
    report_schema=CtasCtesDocument,
    full_filter_schema=CtasCtesFullFilter,  # Usa limit/offset
    lite_filter_schema=CtasCtesLiteFilter,  # No usa limit/offset
    prefix="/ctasCtes",
)

ctas_ctes_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# banco_invico_router = factory.get_router()


# @banco_invico_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
