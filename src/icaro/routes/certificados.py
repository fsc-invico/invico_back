from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    CertificadosDocument,
    CertificadosFullFilter,
    CertificadosLiteFilter,
)
from ..services import CertificadosService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=CertificadosService,
    report_schema=CertificadosDocument,
    full_filter_schema=CertificadosFullFilter,  # Usa limit/offset
    lite_filter_schema=CertificadosLiteFilter,  # No usa limit/offset
    prefix="/certificados",
)

certificados_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
