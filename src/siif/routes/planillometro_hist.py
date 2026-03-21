from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    PlanillometroHistDocument,
    PlanillometroHistFullFilter,
    PlanillometroHistLiteFilter,
)
from ..services import PlanillometroHistService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=PlanillometroHistService,
    report_schema=PlanillometroHistDocument,
    full_filter_schema=PlanillometroHistFullFilter,  # Usa limit/offset
    lite_filter_schema=PlanillometroHistLiteFilter,  # No usa limit/offset
    prefix="/planillometroHist",
)

planillometro_hist_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf610_router = factory.get_router()


# @rf610_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
