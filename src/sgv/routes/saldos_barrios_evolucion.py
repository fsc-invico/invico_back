from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    SaldosBarriosEvolucionDocument,
    SaldosBarriosEvolucionFullFilter,
    SaldosBarriosEvolucionLiteFilter,
)
from ..services import SaldosBarriosEvolucionService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=SaldosBarriosEvolucionService,
    report_schema=SaldosBarriosEvolucionDocument,
    full_filter_schema=SaldosBarriosEvolucionFullFilter,  # Usa limit/offset
    lite_filter_schema=SaldosBarriosEvolucionLiteFilter,  # No usa limit/offset
    prefix="/saldosBarriosEvolucion",
)

saldos_barrios_evolucion_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
