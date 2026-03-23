from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    BancoINVICOSdoFinalDocument,
    BancoINVICOSdoFinalFullFilter,
    BancoINVICOSdoFinalLiteFilter,
)
from ..services import BancoINVICOSdoFinalService  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=BancoINVICOSdoFinalService,
    report_schema=BancoINVICOSdoFinalDocument,
    full_filter_schema=BancoINVICOSdoFinalFullFilter,  # Usa limit/offset
    lite_filter_schema=BancoINVICOSdoFinalLiteFilter,  # No usa limit/offset
    prefix="/bancoINVICOSdoFinal",
)

banco_invico_sdo_final_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# banco_invico_router = factory.get_router()


# @banco_invico_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
