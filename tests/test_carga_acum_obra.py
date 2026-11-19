"""Tests del endpoint agrupado ``/icaro/carga/acumObra`` (CargaService.acum_obra).

La agrupación por actividad/partida/desc_obra con ``importe`` (sum),
``ejercicio`` (min) y ``avance`` (max) se resuelve íntegramente en MongoDB
($match + $group + $project), igual que ``acum_with_desc_siif``, para no
traer documentos crudos al servidor (Koyeb) ni recorrerlos con Pandas.

Cubre:

- Construcción del pipeline (etapas y acumuladores correctos).
- ``limit`` se aplica como etapa ``$limit`` del pipeline (0 u omiso = sin límite).
- ``ejercicio_hasta`` se traduce en ``$lte`` (inclusive) sobre ``ejercicio``.
- ``actividad`` / ``partida`` se filtran como strings (la DB los almacena
  como string y ``format_value`` los convertiría a int).
- Soporte de listas separadas por coma y prefijo ``str:``.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_carga_acum_obra -v
"""

import unittest
from typing import List, Optional

from src.icaro.schemas import CargaAcumObraFilter
from src.icaro.services import CargaService


# -------------------------------------------------
class CursorAgregacionFalso:
    """Cursor asíncrono devuelto por ``collection.aggregate``."""

    # -------------------------------------------------
    def __init__(self, documentos: List[dict]) -> None:
        self.documentos = documentos

    # -------------------------------------------------
    async def to_list(self, length: Optional[int] = None) -> List[dict]:
        return self.documentos


# -------------------------------------------------
class ColeccionFalsa:
    """Colección que registra los pipelines ejecutados por el servicio."""

    # -------------------------------------------------
    def __init__(self, documentos: Optional[List[dict]] = None) -> None:
        self.documentos = documentos or []
        self.pipelines: List[List[dict]] = []

    # -------------------------------------------------
    def aggregate(self, pipeline: List[dict]) -> CursorAgregacionFalso:
        self.pipelines.append(pipeline)
        return CursorAgregacionFalso(self.documentos)


# -------------------------------------------------
class RepositorioCargaFalso:
    """Repositorio en memoria que replica ``collection.aggregate``."""

    # -------------------------------------------------
    def __init__(self, documentos: Optional[List[dict]] = None) -> None:
        self.collection = ColeccionFalsa(documentos)
        self.unique_field: Optional[str] = None


# -------------------------------------------------
def construir_servicio(documentos: Optional[List[dict]] = None) -> CargaService:
    """Instancia el servicio con un repositorio falso (dataclass)."""
    return CargaService(
        repository=RepositorioCargaFalso(documentos),
        rdeu_service=None,
        proveedores_repo=None,
        rf610_service=None,
        retenciones_repo=None,
        informe_contable_repo=None,
        resumen_rend_obras_repo=None,
    )


# -------------------------------------------------
class TestAcumObraPipeline(unittest.IsolatedAsyncioTestCase):
    """El servicio delega la agrupación en un pipeline de MongoDB."""

    # -------------------------------------------------
    async def test_pipeline_agrupa_con_acumuladores_esperados(self) -> None:
        """$match -> $group (sum/min/max) -> $project -> $sort."""
        servicio = construir_servicio()

        await servicio.acum_obra(params=CargaAcumObraFilter())

        pipelines = servicio.repository.collection.pipelines
        self.assertEqual(len(pipelines), 1)
        pipeline = pipelines[0]

        self.assertEqual(
            [list(etapa.keys())[0] for etapa in pipeline],
            ["$match", "$group", "$project", "$sort"],
        )

        grupo = pipeline[1]["$group"]
        self.assertEqual(
            grupo["_id"],
            {
                "actividad": "$actividad",
                "partida": "$partida",
                "desc_obra": "$desc_obra",
            },
        )
        self.assertEqual(grupo["importe"], {"$sum": "$importe"})
        self.assertEqual(grupo["ejercicio"], {"$min": "$ejercicio"})
        self.assertEqual(grupo["avance"], {"$max": "$avance"})

        proyeccion = pipeline[2]["$project"]
        self.assertEqual(proyeccion["_id"], 0)
        self.assertEqual(proyeccion["actividad"], "$_id.actividad")
        self.assertEqual(proyeccion["importe"], 1)

    # -------------------------------------------------
    async def test_devuelve_los_grupos_de_la_base(self) -> None:
        """Los documentos agregados se devuelven tal cual (sin Pandas)."""
        grupos = [
            {
                "actividad": "11-00-02-79",
                "partida": "1100",
                "desc_obra": "Museo",
                "importe": 1500.5,
                "ejercicio": 2024,
                "avance": 80.0,
            }
        ]
        servicio = construir_servicio(grupos)

        resultado = await servicio.acum_obra(params=CargaAcumObraFilter())

        self.assertEqual(resultado, grupos)

    # -------------------------------------------------
    async def test_sin_resultados_devuelve_lista_vacia(self) -> None:
        """Sin documentos que agrupar responde [] (igual que acum_estructura)."""
        servicio = construir_servicio()

        resultado = await servicio.acum_obra(params=CargaAcumObraFilter())

        self.assertEqual(resultado, [])

    # -------------------------------------------------
    async def test_ejercicio_hasta_va_al_match_como_lte(self) -> None:
        """El filtro 'hasta inclusive' termina en la etapa $match."""
        servicio = construir_servicio()

        await servicio.acum_obra(
            params=CargaAcumObraFilter(ejercicio_hasta=2025, partida="421")
        )

        match = servicio.repository.collection.pipelines[0][0]["$match"]
        self.assertEqual(match["ejercicio"], {"$lte": 2025})
        self.assertEqual(match["partida"], "421")

    # -------------------------------------------------
    async def test_limit_se_aplica_como_etapa_limit(self) -> None:
        """limit=100 agrega $limit al final del pipeline: sólo 100 grupos."""
        servicio = construir_servicio()

        await servicio.acum_obra(params=CargaAcumObraFilter(limit=100))

        pipeline = servicio.repository.collection.pipelines[0]
        self.assertEqual(pipeline[-1], {"$limit": 100})

    # -------------------------------------------------
    async def test_limit_cero_o_omitido_no_trunca(self) -> None:
        """Sin limit (o en 0) no hay etapa $limit: se devuelven todos."""
        servicio = construir_servicio()

        await servicio.acum_obra(params=CargaAcumObraFilter(limit=0))
        await servicio.acum_obra(params=CargaAcumObraFilter())

        for pipeline in servicio.repository.collection.pipelines:
            self.assertNotIn("$limit", [list(etapa.keys())[0] for etapa in pipeline])
            self.assertEqual(list(pipeline[-1].keys()), ["$sort"])


# -------------------------------------------------
class TestCargaAcumObraFilter(unittest.TestCase):
    """La traducción query params -> filtro MongoDB de CargaAcumObraFilter."""

    # -------------------------------------------------
    def test_sin_filtros_devuelve_filtro_vacio(self) -> None:
        """Sin parámetros el filtro es vacío (MongoDB matchea todo)."""
        self.assertEqual(CargaAcumObraFilter().get_full_filter(), {})

    # -------------------------------------------------
    def test_ejercicio_hasta_es_lte_inclusive(self) -> None:
        """ejercicio_hasta se traduce en $lte (inclusive) sobre 'ejercicio'."""
        filtro = CargaAcumObraFilter(ejercicio_hasta=2025).get_full_filter()

        self.assertEqual(filtro, {"ejercicio": {"$lte": 2025}})

    # -------------------------------------------------
    def test_limit_no_forma_parte_del_filtro_mongo(self) -> None:
        """limit es de paginación: no debe colarse en el $match."""
        filtro = CargaAcumObraFilter(limit=100, ejercicio_hasta=2025).get_full_filter()

        self.assertNotIn("limit", filtro)
        self.assertEqual(filtro, {"ejercicio": {"$lte": 2025}})

    # -------------------------------------------------
    def test_actividad_y_partida_se_conservan_como_texto(self) -> None:
        """No se convierten a int: en icaro_carga son strings."""
        filtro = CargaAcumObraFilter(actividad="100", partida="421").get_full_filter()

        self.assertIsInstance(filtro["actividad"], str)
        self.assertIsInstance(filtro["partida"], str)
        self.assertEqual(filtro["actividad"], "100")
        self.assertEqual(filtro["partida"], "421")

    # -------------------------------------------------
    def test_listas_separadas_por_coma_generan_in_de_textos(self) -> None:
        """Varios valores (ej: 421,442) se resuelven como $in de strings."""
        filtro = CargaAcumObraFilter(partida="421,442").get_full_filter()

        self.assertEqual(filtro["partida"], {"$in": ["421", "442"]})

    # -------------------------------------------------
    def test_acepta_prefijo_str_y_recorta_espacios(self) -> None:
        """Soporta la convención 'str:' y espacios sobrantes de los params."""
        filtro = CargaAcumObraFilter(partida=" str:421 ").get_full_filter()

        self.assertEqual(filtro["partida"], "421")

    # -------------------------------------------------
    def test_valores_vacios_no_generan_filtro(self) -> None:
        """Un param vacío (actividad=) no debe filtrar por la cadena vacía."""
        filtro = CargaAcumObraFilter(actividad="", partida=" , ").get_full_filter()

        self.assertNotIn("actividad", filtro)
        self.assertNotIn("partida", filtro)


# -------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
