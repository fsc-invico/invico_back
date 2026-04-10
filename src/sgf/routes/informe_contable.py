from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    InformeContableDocument,
    InformeContableFullFilter,
    InformeContableLiteFilter,
)
from ..services import InformeContableService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=InformeContableService,
    report_schema=InformeContableDocument,
    full_filter_schema=InformeContableFullFilter,  # Usa limit/offset
    lite_filter_schema=InformeContableLiteFilter,  # No usa limit/offset
    prefix="/informeContable",
)

informe_contable_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# resumen_rend_prov_router = factory.get_router()


# @resumen_rend_prov_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
