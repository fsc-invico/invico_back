"""Tests de ``ControlViaticosService.compute_control_rendicion``.

El cruce se arma partiendo de ``siif_rendicion`` (partida 372); con un
merge ``left`` los ``nro_expte`` que solo existen en el banco (``sscc``)
quedaban fuera del resultado. Cubre:

- Expediente solo en sscc -> se incluye con las columnas ``siif_`` en 0.
- Expediente con reembolso 373 pero sin rendición 372 -> conserva
  ``siif_reembolso``.
- Lados vacíos (sin SIIF / sin banco / sin datos) -> no truena.
- Cada fila valida contra ``ControlViaticosRendicionReport``
  (``ejercicio`` debe ser entero, no float).

Ejecutar desde la raíz del proyecto:

    python -m unittest tests.test_control_viaticos_compute -v
"""

import asyncio
import unittest
from typing import Dict, List

import pandas as pd

from src.analysis.schemas import (
    ControlViaticosFilter,
    ControlViaticosRendicionReport,
)
from src.analysis.services.control_viaticos import (
    NRO_EXPTE_PLACEHOLDER,
    ControlViaticosService,
)

EJERCICIO: int = 2024
EXPTE_RENDICION: str = "90000012024"
EXPTE_REEMBOLSO: str = "90000022024"
EXPTE_SOLO_BANCO: str = "90000032024"


# -------------------------------------------------
def _crear_servicio(
    fondos: pd.DataFrame,
    gastos: pd.DataFrame,
    banco: pd.DataFrame,
) -> ControlViaticosService:
    """Instancia el servicio con los ``generate_*`` mockeados.

    Los tres DataFrames crudos son lo que devolverían
    ``generate_siif_fondo``, ``generate_siif_gastos`` y
    ``generate_banco`` (banco ya con importes en positivo).
    """
    servicio = ControlViaticosService(
        control_rendicion_repo=None,
        rfondos04_service=None,
        gastos_service=None,
        banco_service=None,
    )

    async def _fondos(ejercicio: int) -> pd.DataFrame:
        return fondos

    async def _gastos(ejercicio: int) -> pd.DataFrame:
        return gastos

    async def _banco(ejercicio: int) -> pd.DataFrame:
        return banco

    servicio.generate_siif_fondo = _fondos
    servicio.generate_siif_gastos = _gastos
    servicio.generate_banco = _banco
    return servicio


# -------------------------------------------------
def _datos_completos() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Fondos F1/F2, gastos 372+373 y banco con expediente propio."""
    fondos = pd.DataFrame(
        [
            {"nro_fondo": "F1", "tipo_comprobante": "PA3", "importe": 100.0},
            {"nro_fondo": "F2", "tipo_comprobante": "PA3", "importe": 50.0},
        ]
    )
    gastos = pd.DataFrame(
        [
            {
                "ejercicio": EJERCICIO,
                "nro_expte": EXPTE_RENDICION,
                "nro_fondo": "F1",
                "partida": "372",
                "importe": 60.0,
            },
            {
                "ejercicio": EJERCICIO,
                "nro_expte": EXPTE_REEMBOLSO,
                "nro_fondo": "F2",
                "partida": "373",
                "importe": 20.0,
            },
        ]
    )
    banco = pd.DataFrame(
        [
            {
                "nro_expte": EXPTE_REEMBOLSO,
                "cod_imputacion": "029",
                "importe": 30.0,
            },
            {
                "nro_expte": EXPTE_SOLO_BANCO,
                "cod_imputacion": "040",
                "importe": 25.0,
            },
        ]
    )
    return fondos, gastos, banco


# -------------------------------------------------
def _calcular(servicio: ControlViaticosService) -> List[dict]:
    params = ControlViaticosFilter(ejercicio=EJERCICIO)
    return asyncio.run(servicio.compute_control_rendicion(params=params))


# -------------------------------------------------
class TestComputeControlRendicion(unittest.TestCase):
    """Cruce Anticipo/Rendición de Viáticos on-demand."""

    # -------------------------------------------------
    def test_incluye_expediente_solo_en_banco(self) -> None:
        """Un nro_expte sin rendición 372 pero con movimiento en el
        banco debe aparecer con las columnas ``siif_`` en 0."""
        fondos, gastos, banco = _datos_completos()
        servicio = _crear_servicio(fondos=fondos, gastos=gastos, banco=banco)

        filas: Dict[str, dict] = {
            f["nro_expte"]: f for f in _calcular(servicio)
        }

        self.assertEqual(
            set(filas), {EXPTE_RENDICION, EXPTE_REEMBOLSO, EXPTE_SOLO_BANCO}
        )
        solo_banco = filas[EXPTE_SOLO_BANCO]
        self.assertEqual(solo_banco["ejercicio"], EJERCICIO)
        self.assertIsInstance(solo_banco["ejercicio"], int)
        self.assertEqual(solo_banco["siif_anticipo"], 0.0)
        self.assertEqual(solo_banco["siif_rendicion"], 0.0)
        self.assertEqual(solo_banco["siif_reversion"], 0.0)
        self.assertEqual(solo_banco["siif_reembolso"], 0.0)
        self.assertEqual(solo_banco["siif_saldo_anticipo"], 0.0)
        self.assertEqual(solo_banco["siif_gasto_total"], 0.0)
        self.assertEqual(solo_banco["sscc_gasto_total"], 25.0)
        self.assertEqual(solo_banco["dif_gasto_total"], -25.0)

    # -------------------------------------------------
    def test_mantiene_importes_de_los_dos_lados(self) -> None:
        """Los expedientes con datos en ambos lados conservan sus
        importes y las diferencias calculadas."""
        fondos, gastos, banco = _datos_completos()
        servicio = _crear_servicio(fondos=fondos, gastos=gastos, banco=banco)

        filas: Dict[str, dict] = {
            f["nro_expte"]: f for f in _calcular(servicio)
        }

        rendicion = filas[EXPTE_RENDICION]
        self.assertEqual(rendicion["siif_anticipo"], 100.0)
        self.assertEqual(rendicion["siif_rendicion"], 60.0)
        self.assertEqual(rendicion["siif_saldo_anticipo"], 40.0)
        self.assertEqual(rendicion["sscc_gasto_total"], 0.0)
        self.assertEqual(rendicion["dif_gasto_total"], 60.0)

        reembolso = filas[EXPTE_REEMBOLSO]
        self.assertEqual(reembolso["siif_reembolso"], 20.0)
        self.assertEqual(reembolso["siif_rendicion"], 0.0)
        self.assertEqual(reembolso["siif_gasto_total"], 20.0)
        self.assertEqual(reembolso["sscc_anticipo"], 30.0)
        self.assertEqual(reembolso["dif_gasto_total"], -10.0)

    # -------------------------------------------------
    def test_filas_validan_contra_el_reporte(self) -> None:
        """Cada fila del cruce debe ser un reporte válido (``ejercicio``
        entero y todos los importes presentes)."""
        fondos, gastos, banco = _datos_completos()
        servicio = _crear_servicio(fondos=fondos, gastos=gastos, banco=banco)

        for fila in _calcular(servicio):
            ControlViaticosRendicionReport(**fila)

    # -------------------------------------------------
    def test_siif_vacio_incluye_banco(self) -> None:
        """Sin datos de SIIF el cruce no queda vacío: aparecen los
        expedientes del banco con todos los importes en 0."""
        _, _, banco = _datos_completos()
        servicio = _crear_servicio(
            fondos=pd.DataFrame(columns=["nro_fondo", "tipo_comprobante", "importe"]),
            gastos=pd.DataFrame(
                columns=["ejercicio", "nro_expte", "nro_fondo", "partida", "importe"]
            ),
            banco=banco,
        )

        filas: Dict[str, dict] = {
            f["nro_expte"]: f for f in _calcular(servicio)
        }

        self.assertEqual(set(filas), {EXPTE_REEMBOLSO, EXPTE_SOLO_BANCO})
        for fila in filas.values():
            self.assertEqual(fila["ejercicio"], EJERCICIO)
            self.assertIsInstance(fila["ejercicio"], int)
            self.assertEqual(fila["siif_anticipo"], 0.0)
            self.assertEqual(fila["siif_gasto_total"], 0.0)
            ControlViaticosRendicionReport(**fila)

    # -------------------------------------------------
    def test_banco_vacio_mantiene_siif(self) -> None:
        """Sin movimientos de banco los expedientes de SIIF siguen
        apareciendo con los importes ``sscc_`` en 0."""
        fondos, gastos, _ = _datos_completos()
        servicio = _crear_servicio(
            fondos=fondos,
            gastos=gastos,
            banco=pd.DataFrame(columns=["nro_expte", "cod_imputacion", "importe"]),
        )

        filas: Dict[str, dict] = {
            f["nro_expte"]: f for f in _calcular(servicio)
        }

        self.assertEqual(set(filas), {EXPTE_RENDICION, EXPTE_REEMBOLSO})
        rendicion = filas[EXPTE_RENDICION]
        self.assertEqual(rendicion["siif_gasto_total"], 60.0)
        self.assertEqual(rendicion["sscc_gasto_total"], 0.0)
        self.assertEqual(rendicion["dif_gasto_total"], 60.0)

    # -------------------------------------------------
    def test_banco_sin_expte_usa_placeholder(self) -> None:
        """Los movimientos sin expediente extraíble (``nro_expte`` None)
        se incluyen agrupados bajo ``NRO_EXPTE_PLACEHOLDER``: el
        ``groupby`` descartaba las claves NaN y los perdía."""
        fondos, gastos, banco = _datos_completos()
        banco = pd.concat(
            [
                banco,
                pd.DataFrame(
                    [
                        {
                            "nro_expte": None,
                            "cod_imputacion": "029",
                            "importe": 10.0,
                        },
                        {
                            "nro_expte": None,
                            "cod_imputacion": "040",
                            "importe": 5.0,
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )
        servicio = _crear_servicio(fondos=fondos, gastos=gastos, banco=banco)

        filas: Dict[str, dict] = {
            f["nro_expte"]: f for f in _calcular(servicio)
        }

        self.assertIn(NRO_EXPTE_PLACEHOLDER, filas)
        placeholder = filas[NRO_EXPTE_PLACEHOLDER]
        # Ambos movimientos sin expediente van en una sola fila.
        self.assertEqual(placeholder["sscc_anticipo"], 10.0)
        self.assertEqual(placeholder["sscc_reembolso"], 5.0)
        self.assertEqual(placeholder["sscc_gasto_total"], 15.0)
        self.assertEqual(placeholder["siif_anticipo"], 0.0)
        self.assertEqual(placeholder["siif_gasto_total"], 0.0)
        self.assertEqual(placeholder["dif_gasto_total"], -15.0)
        self.assertEqual(placeholder["ejercicio"], EJERCICIO)
        ControlViaticosRendicionReport(**placeholder)

    # -------------------------------------------------
    def test_todo_vacio_devuelve_lista_vacia(self) -> None:
        """Sin datos de ningún sistema se devuelve ``[]`` sin truenar."""
        servicio = _crear_servicio(
            fondos=pd.DataFrame(columns=["nro_fondo", "tipo_comprobante", "importe"]),
            gastos=pd.DataFrame(
                columns=["ejercicio", "nro_expte", "nro_fondo", "partida", "importe"]
            ),
            banco=pd.DataFrame(columns=["nro_expte", "cod_imputacion", "importe"]),
        )

        self.assertEqual(_calcular(servicio), [])


if __name__ == "__main__":
    unittest.main()

