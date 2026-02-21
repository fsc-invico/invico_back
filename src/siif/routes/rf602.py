from ...utils.router_factory import GenericRouterFactory
from ..services import Rf602Service  # La clase del servicio

factory = GenericRouterFactory(
    service_dependency=Rf602Service, prefix="/rf602"
)

rf602_router = factory.get_router()

# # Si necesitas agregar una ruta personalizada que NO esté en la base:
# rf602_router = factory.get_router()


# @rf602_router.get("/custom-stats")
# async def get_stats():
#     return {"stats": "data"}
