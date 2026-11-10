"""Tests de la unificación de cta_cte en el backend (CtasCtesService).

Garantías verificadas (paridad con ``cta_cte_unifier`` del frontend):

- Sin match: se conserva la ``cta_cte`` que trae el dataframe original.
- Match inválido (``map_to`` nulo, vacío o ``"NA"``): se conserva el
  original; nunca se pisa el dato de origen con basura.
- El nexo ``"NA"``/vacío no se usa como clave de mapeo.
- Ante nexo duplicado gana el primer documento (``_id`` asc), igual que
  ``drop_duplicates(keep="first")`` del front.
- La query filtra nulos con ``$exists``/``$ne`` y proyecta solo las
  claves; el cursor se ordena por ``_id`` asc.
- DataFrames vacíos o sin la columna ``cta_cte`` se devuelven tal cual.

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_ctas_cte_unifier -v
"""

import unittest
from typing import List, Optional

import pandas as pd

from src.sscc.services.ctas_ctes import CtasCtesService


# -------------------------------------------------
class CursorFalso:
    """Cursor async mínimo: registra el sort y devuelve los documentos."""

    def __init__(self, docs: List[dict]) -> None:
        self._docs = docs
        self.sort_llamado: Optional[tuple] = None

    # -------------------------------------------------
    def sort(self, campo: str, direccion: int) -> "CursorFalso":
        self.sort_llamado = (campo, direccion)
        self._docs = sorted(self._docs, key=lambda doc: str(doc.get("_id", "")))
        return self

    # -------------------------------------------------
    async def to_list(self, length: Optional[int] = None) -> List[dict]:
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])


# -------------------------------------------------
class CollectionFalsa:
    """Interpreta el filtro Mongo simple de ``cta_cte_unifier``:

    ``{campo: {"$exists": True, "$ne": None}}`` → se excluye el documento
    si el campo falta o es ``None`` (como hace MongoDB con ``$ne: null``).
    """

    def __init__(self, docs: List[dict]) -> None:
        self._docs = docs
        self.ultimo_filtro: dict = {}
        self.ultima_proyeccion: Optional[dict] = None
        self.ultimo_cursor: Optional[CursorFalso] = None

    # -------------------------------------------------
    def find(
        self, filtro: Optional[dict] = None, proyeccion: Optional[dict] = None
    ) -> CursorFalso:
        self.ultimo_filtro = filtro or {}
        self.ultima_proyeccion = proyeccion

        docs: List[dict] = []
        for doc in self._docs:
            incluir = True
            for campo, condicion in self.ultimo_filtro.items():
                if not isinstance(condicion, dict):
                    continue
                if condicion.get("$exists") and campo not in doc:
                    incluir = False
                if "$ne" in condicion and doc.get(campo) is None:
                    incluir = False
            if incluir:
                docs.append(dict(doc))

        self.ultimo_cursor = CursorFalso(docs)
        return self.ultimo_cursor


# -------------------------------------------------
class RepositorioFalso:
    """Repositorio mínimo con la interfaz ``collection.find`` del real."""

    def __init__(self, docs: List[dict]) -> None:
        self.collection = CollectionFalsa(docs)


# -------------------------------------------------
def construir_servicio(docs: List[dict]) -> CtasCtesService:
    return CtasCtesService(repository=RepositorioFalso(docs))


# -------------------------------------------------
def obtener_cursor(servicio: CtasCtesService) -> CursorFalso:
    collection = servicio.repository.collection
    assert collection.ultimo_cursor is not None
    return collection.ultimo_cursor


# -------------------------------------------------
class TestCtaCteUnifier(unittest.IsolatedAsyncioTestCase):
    """Conservación del original y reglas del mapping."""

    # -------------------------------------------------
    async def test_sin_match_conserva_el_original(self) -> None:
        """Sin coincidencia en el nexo queda la cta_cte de origen."""
        servicio = construir_servicio(
            [{"_id": "1", "sgf_cta_cte": "999", "map_to": "111"}]
        )
        df = pd.DataFrame({"cta_cte": ["10158", "zzz"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["10158", "zzz"])
        # El DataFrame recibido no se muta (se trabaja sobre una copia)
        self.assertEqual(df["cta_cte"].tolist(), ["10158", "zzz"])

    # -------------------------------------------------
    async def test_match_valido_reemplaza(self) -> None:
        """Un map_to real sí homologa la cuenta."""
        servicio = construir_servicio(
            [{"_id": "1", "sgf_cta_cte": "10158", "map_to": "111"}]
        )
        df = pd.DataFrame({"cta_cte": ["10158", "zzz"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["111", "zzz"])

    # -------------------------------------------------
    async def test_map_to_vacio_o_na_conserva_original(self) -> None:
        """map_to vacío o "NA" no aporta cruce: se conserva el original."""
        servicio = construir_servicio(
            [
                {"_id": "1", "sgf_cta_cte": "A", "map_to": ""},
                {"_id": "2", "sgf_cta_cte": "B", "map_to": "NA"},
            ]
        )
        df = pd.DataFrame({"cta_cte": ["A", "B"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["A", "B"])

    # -------------------------------------------------
    async def test_map_to_nulo_conserva_original(self) -> None:
        """map_to None (dato histórico) no pisa el valor de origen."""
        servicio = construir_servicio(
            [{"_id": "1", "sgf_cta_cte": "A", "map_to": None}]
        )
        df = pd.DataFrame({"cta_cte": ["A"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["A"])

    # -------------------------------------------------
    async def test_nexo_na_no_se_usa_como_clave(self) -> None:
        """Un nexo "NA" no debe convertir el "NA" del df en otra cuenta."""
        servicio = construir_servicio(
            [{"_id": "1", "sgf_cta_cte": "NA", "map_to": "111"}]
        )
        df = pd.DataFrame({"cta_cte": ["NA"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["NA"])

    # -------------------------------------------------
    async def test_mezcla_match_valido_sin_match_e_invalido(self) -> None:
        """Cada fila se resuelve por separado: match → mapea; si no, original."""
        servicio = construir_servicio(
            [
                {"_id": "1", "sgf_cta_cte": "10158", "map_to": "111"},
                {"_id": "2", "sgf_cta_cte": "B", "map_to": "NA"},
            ]
        )
        df = pd.DataFrame({"cta_cte": ["10158", "B", "zzz"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["111", "B", "zzz"])

    # -------------------------------------------------
    async def test_duplicados_gana_el_primer_id(self) -> None:
        """Ante nexo duplicado gana el primer _id (keep="first" del front)."""
        servicio = construir_servicio(
            [
                {"_id": "2", "sgf_cta_cte": "DUP", "map_to": "segundo"},
                {"_id": "1", "sgf_cta_cte": "DUP", "map_to": "primero"},
            ]
        )
        df = pd.DataFrame({"cta_cte": ["DUP"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["primero"])
        self.assertEqual(obtener_cursor(servicio).sort_llamado, ("_id", 1))

    # -------------------------------------------------
    async def test_query_filtra_nulos_y_proyecta(self) -> None:
        """La query descarta nexo ausente/null y proyecta solo claves."""
        servicio = construir_servicio(
            [
                {"_id": "1", "sgf_cta_cte": None, "map_to": "x"},
                {"_id": "2", "map_to": "y"},  # sin campo nexo
                {"_id": "3", "sgf_cta_cte": "OK", "map_to": "111"},
            ]
        )
        df = pd.DataFrame({"cta_cte": ["OK"]})

        resultado = await servicio.cta_cte_unifier(df, "sgf_cta_cte")

        self.assertEqual(resultado["cta_cte"].tolist(), ["111"])
        collection = servicio.repository.collection
        self.assertEqual(
            collection.ultimo_filtro,
            {"sgf_cta_cte": {"$exists": True, "$ne": None}},
        )
        self.assertEqual(
            collection.ultima_proyeccion, {"map_to": 1, "sgf_cta_cte": 1, "_id": 0}
        )

    # -------------------------------------------------
    async def test_df_vacio_o_sin_columna_se_devuelve_tal_cual(self) -> None:
        """Sin datos o sin columna cta_cte no se intenta unificar."""
        servicio = construir_servicio([])

        vacio = pd.DataFrame()
        self.assertIs(await servicio.cta_cte_unifier(vacio, "sgf_cta_cte"), vacio)

        sin_columna = pd.DataFrame({"importe": [1.0]})
        self.assertIs(
            await servicio.cta_cte_unifier(sin_columna, "sgf_cta_cte"),
            sin_columna,
        )


if __name__ == "__main__":
    unittest.main()