"""
MÓDULO DE ANÁLISIS ESTADÍSTICO AVANZADO
=======================================
Analizador Inteligente 1-49 v0.4

Análisis estadístico profundo para generar las TOP 5 combinaciones
basadas en datos históricos reales.
"""

import numpy as np
import pandas as pd
from itertools import combinations
from collections import Counter
from datetime import datetime
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass

from importador import COLUMNAS


@dataclass
class CombinacionEstadistica:
    """Representa una combinación con su análisis estadístico."""
    numeros: List[int]  # 5 números ordenados
    puntuacion_total: float
    detalle_puntuaciones: Dict[str, float]
    explicacion: str
    frecuencia_numeros: Dict[int, int]
    parejas_en_combinacion: List[Tuple[Tuple[int, int], int]]
    trios_en_combinacion: List[Tuple[Tuple[int, int, int], int]]


def calcular_frecuencias(df: pd.DataFrame) -> pd.Series:
    """Calcula la frecuencia de cada número (1-49) en los sorteos principales."""
    principales = df[["n1", "n2", "n3", "n4", "n5"]].astype(int)
    todos = principales.to_numpy().flatten()
    return pd.Series(todos).value_counts().reindex(range(1, 50), fill_value=0)


def calcular_frecuencias_por_dia(df: pd.DataFrame) -> Dict[int, pd.Series]:
    """
    Calcula la frecuencia de números por día de la semana (0=Lunes, 6=Domingo).
    Retorna dict {dia_semana: Series con frecuencias}.
    Si no hay fechas válidas, retorna dict con Series de ceros.
    """
    if not _validar_fechas_disponibles(df):
        return {dia: pd.Series(0, index=range(1, 50), dtype=int) for dia in range(7)}

    df = df.copy()
    df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha_dt"])
    if df.empty:
        return {dia: pd.Series(0, index=range(1, 50), dtype=int) for dia in range(7)}
    df["dia_semana"] = df["fecha_dt"].dt.dayofweek  # 0=Lunes

    frecuencias_por_dia = {}
    for dia in range(7):
        df_dia = df[df["dia_semana"] == dia]
        if len(df_dia) > 0:
            principales = df_dia[["n1", "n2", "n3", "n4", "n5"]].astype(int)
            todos = principales.to_numpy().flatten()
            freq = pd.Series(todos).value_counts().reindex(range(1, 50), fill_value=0)
        else:
            freq = pd.Series(0, index=range(1, 50), dtype=int)
        frecuencias_por_dia[dia] = freq
    return frecuencias_por_dia


def calcular_parejas_trios(df: pd.DataFrame, top_n: int = 50) -> Tuple[Counter, Counter]:
    """Calcula las parejas y tríos más frecuentes."""
    principales = df[["n1", "n2", "n3", "n4", "n5"]].astype(int)
    contador_parejas = Counter()
    contador_trios = Counter()

    for fila in principales.to_numpy():
        numeros = sorted(map(int, fila))
        contador_parejas.update(combinations(numeros, 2))
        contador_trios.update(combinations(numeros, 3))

    return contador_parejas.most_common(top_n), contador_trios.most_common(top_n)


def calcular_frecuencias_recientes(df: pd.DataFrame, ultimos_n: int = 20) -> pd.Series:
    """Calcula frecuencias de los últimos N sorteos."""
    df_reciente = df.head(ultimos_n)  # El CSV está ordenado descendente por fecha
    principales = df_reciente[["n1", "n2", "n3", "n4", "n5"]].astype(int)
    todos = principales.to_numpy().flatten()
    return pd.Series(todos).value_counts().reindex(range(1, 50), fill_value=0)


def _validar_fechas_disponibles(df: pd.DataFrame) -> bool:
    """Verifica si hay fechas válidas en el DataFrame."""
    if "fecha" not in df.columns:
        return False
    fechas = pd.to_datetime(df["fecha"], errors="coerce")
    return fechas.notna().any()


def detectar_numeros_consecutivos_dias(df: pd.DataFrame) -> Dict[int, int]:
    """
    Detecta números que aparecen en días consecutivos.
    Retorna dict {numero: max_dias_consecutivos}.
    Si no hay fechas válidas, retorna dict con ceros.
    """
    if not _validar_fechas_disponibles(df):
        return {n: 0 for n in range(1, 50)}

    df = df.copy()
    df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha_dt"])
    if df.empty:
        return {n: 0 for n in range(1, 50)}
    df = df.sort_values("fecha_dt")

    max_consecutivos = {n: 0 for n in range(1, 50)}

    for numero in range(1, 50):
        apariciones = []
        for _, fila in df.iterrows():
            principales = [fila["n1"], fila["n2"], fila["n3"], fila["n4"], fila["n5"]]
            if numero in principales:
                apariciones.append(fila["fecha_dt"])

        if len(apariciones) < 2:
            continue

        racha_actual = 1
        max_racha = 1
        for i in range(1, len(apariciones)):
            diff = (apariciones[i] - apariciones[i-1]).days
            if diff == 1:
                racha_actual += 1
                max_racha = max(max_racha, racha_actual)
            else:
                racha_actual = 1
        max_consecutivos[numero] = max_racha

    return max_consecutivos


def calcular_parejas_consecutivas_dias(df: pd.DataFrame) -> Dict[Tuple[int, int], int]:
    """
    Detecta parejas que aparecen juntas en días consecutivos.
    Retorna dict {(num1, num2): max_dias_consecutivos}.
    Si no hay fechas válidas, retorna dict vacío.
    """
    if not _validar_fechas_disponibles(df):
        return {}

    df = df.copy()
    df["fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha_dt"])
    if df.empty:
        return {}
    df = df.sort_values("fecha_dt")

    max_consecutivos = {}

    for _, fila in df.iterrows():
        principales = sorted([fila["n1"], fila["n2"], fila["n3"], fila["n4"], fila["n5"]])
        for pareja in combinations(principales, 2):
            if pareja not in max_consecutivos:
                max_consecutivos[pareja] = 0

    for pareja in max_consecutivos:
        apariciones = []
        for _, fila in df.iterrows():
            principales = [fila["n1"], fila["n2"], fila["n3"], fila["n4"], fila["n5"]]
            if pareja[0] in principales and pareja[1] in principales:
                apariciones.append(fila["fecha_dt"])

        if len(apariciones) < 2:
            max_consecutivos[pareja] = 0
            continue

        racha_actual = 1
        max_racha = 1
        for i in range(1, len(apariciones)):
            diff = (apariciones[i] - apariciones[i-1]).days
            if diff == 1:
                racha_actual += 1
                max_racha = max(max_racha, racha_actual)
            else:
                racha_actual = 1
        max_consecutivos[pareja] = max_racha

    return max_consecutivos


def calcular_puntuacion_combinacion(
    combinacion: List[int],
    frecuencias: pd.Series,
    frecuencias_recientes: pd.Series,
    pares: Dict[Tuple[int, int], int],
    trios: Dict[Tuple[int, int, int], int],
    consecutivos_dias: Dict[int, int],
    pares_consecutivos: Dict[Tuple[int, int], int],
    dia_semana_actual: int,
    frecuencias_por_dia: Dict[int, pd.Series],
    pesos: Dict[str, float] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Calcula la puntuación estadística de una combinación.
    Retorna (puntuación_total, detalle_puntuaciones).
    """
    if pesos is None:
        pesos = {
            "frecuencia_global": 1.0,
            "frecuencia_reciente": 1.5,
            "frecuencia_dia_semana": 1.2,
            "parejas_frecuentes": 2.0,
            "trios_frecuentes": 2.5,
            "consecutivos_dias": 1.8,
            "pares_consecutivos": 2.0,
            "equilibrio_pares_impares": 0.5,
            "equilibrio_altos_bajos": 0.5,
        }

    combinacion = sorted(combinacion)
    puntuaciones = {}

    # 1. Frecuencia global
    freq_global = sum(frecuencias[n] for n in combinacion)
    max_freq_global = 5 * frecuencias.max() if frecuencias.max() > 0 else 1
    puntuaciones["frecuencia_global"] = (freq_global / max_freq_global) * 100 * pesos["frecuencia_global"]

    # 2. Frecuencia reciente
    freq_reciente = sum(frecuencias_recientes[n] for n in combinacion)
    max_freq_reciente = 5 * frecuencias_recientes.max() if frecuencias_recientes.max() > 0 else 1
    puntuaciones["frecuencia_reciente"] = (freq_reciente / max_freq_reciente) * 100 * pesos["frecuencia_reciente"]

    # 3. Frecuencia por día de la semana
    freq_dia = frecuencias_por_dia.get(dia_semana_actual, pd.Series(0, index=range(1, 50)))
    freq_dia_semana = sum(freq_dia[n] for n in combinacion)
    max_freq_dia = 5 * freq_dia.max() if freq_dia.max() > 0 else 1
    puntuaciones["frecuencia_dia_semana"] = (freq_dia_semana / max_freq_dia) * 100 * pesos["frecuencia_dia_semana"]

    # 4. Parejas frecuentes
    pares_en_comb = list(combinations(combinacion, 2))
    score_pares = sum(pares.get(p, 0) for p in pares_en_comb)
    max_pares = 10 * max(pares.values()) if pares else 1
    puntuaciones["parejas_frecuentes"] = (score_pares / max_pares) * 100 * pesos["parejas_frecuentes"]

    # 5. Tríos frecuentes
    trios_en_comb = list(combinations(combinacion, 3))
    score_trios = sum(trios.get(t, 0) for t in trios_en_comb)
    max_trios = 10 * max(trios.values()) if trios else 1
    puntuaciones["trios_frecuentes"] = (score_trios / max_trios) * 100 * pesos["trios_frecuentes"]

    # 6. Números consecutivos en días
    score_consec = sum(consecutivos_dias.get(n, 0) for n in combinacion)
    max_consec = 5 * max(consecutivos_dias.values()) if consecutivos_dias.values() else 1
    if max_consec == 0:
        max_consec = 1
    puntuaciones["consecutivos_dias"] = (score_consec / max_consec) * 100 * pesos["consecutivos_dias"]

    # 7. Parejas consecutivas en días
    score_pares_consec = sum(pares_consecutivos.get(p, 0) for p in pares_en_comb)
    max_pares_consec = 10 * max(pares_consecutivos.values()) if pares_consecutivos.values() else 1
    if max_pares_consec == 0:
        max_pares_consec = 1
    puntuaciones["pares_consecutivos"] = (score_pares_consec / max_pares_consec) * 100 * pesos["pares_consecutivos"]

    # 8. Equilibrio pares/impares
    pares_count = sum(1 for n in combinacion if n % 2 == 0)
    if pares_count in [2, 3]:
        puntuaciones["equilibrio_pares_impares"] = 100 * pesos["equilibrio_pares_impares"]
    elif pares_count in [1, 4]:
        puntuaciones["equilibrio_pares_impares"] = 50 * pesos["equilibrio_pares_impares"]
    else:
        puntuaciones["equilibrio_pares_impares"] = 10 * pesos["equilibrio_pares_impares"]

    # 9. Equilibrio altos/bajos
    bajos_count = sum(1 for n in combinacion if n <= 24)
    if bajos_count in [2, 3]:
        puntuaciones["equilibrio_altos_bajos"] = 100 * pesos["equilibrio_altos_bajos"]
    elif bajos_count in [1, 4]:
        puntuaciones["equilibrio_altos_bajos"] = 50 * pesos["equilibrio_altos_bajos"]
    else:
        puntuaciones["equilibrio_altos_bajos"] = 10 * pesos["equilibrio_altos_bajos"]

    total = sum(puntuaciones.values())
    return total, puntuaciones


def generar_combinaciones_candidatas(
    frecuencias: pd.Series,
    pares: Dict[Tuple[int, int], int],
    trios: Dict[Tuple[int, int, int], int],
    n_candidatas: int = 500
) -> List[List[int]]:
    """
    Genera combinaciones candidatas usando números con mayor frecuencia
    y parejas/tríos frecuentes.
    """
    top_numeros = frecuencias.nlargest(20).index.tolist()
    top_pares = [p for p, _ in list(pares.items())[:30]]
    top_trios = [t for t, _ in list(trios.items())[:20]]

    candidatos = set()
    rng = np.random.default_rng()

    # Estrategia 1: Basadas en top números
    while len(candidatos) < n_candidatas // 3:
        comb = sorted(rng.choice(top_numeros, size=5, replace=False).tolist())
        candidatos.add(tuple(comb))

    # Estrategia 2: Extender top parejas
    for pareja in top_pares[:15]:
        while len(candidatos) < n_candidatas * 2 // 3:
            restantes = [n for n in top_numeros if n not in pareja]
            if len(restantes) >= 3:
                extra = sorted(rng.choice(restantes, size=3, replace=False).tolist())
                comb = sorted(list(pareja) + extra)
                candidatos.add(tuple(comb))
            else:
                break

    # Estrategia 3: Extender top tríos
    for trio in top_trios[:10]:
        while len(candidatos) < n_candidatas:
            restantes = [n for n in top_numeros if n not in trio]
            if len(restantes) >= 2:
                extra = sorted(rng.choice(restantes, size=2, replace=False).tolist())
                comb = sorted(list(trio) + extra)
                candidatos.add(tuple(comb))
            else:
                break

    # Completar con aleatorias si faltan
    while len(candidatos) < n_candidatas:
        comb = sorted(rng.choice(range(1, 50), size=5, replace=False).tolist())
        candidatos.add(tuple(comb))

    return [list(c) for c in list(candidatos)[:n_candidatas]]


def obtener_top_5_combinaciones(df: pd.DataFrame) -> List[CombinacionEstadistica]:
    """
    Función principal: analiza todos los datos y retorna las TOP 5 combinaciones
    con su análisis estadístico completo.
    """
    if len(df) < 10:
        return []

    frecuencias = calcular_frecuencias(df)
    frecuencias_recientes = calcular_frecuencias_recientes(df, 20)
    pares_lista, trios_lista = calcular_parejas_trios(df, 100)
    pares = dict(pares_lista)
    trios = dict(trios_lista)
    consecutivos_dias = detectar_numeros_consecutivos_dias(df)
    pares_consecutivos = calcular_parejas_consecutivas_dias(df)
    frecuencias_por_dia = calcular_frecuencias_por_dia(df)

    hoy = datetime.now()
    dia_semana_actual = hoy.weekday()

    candidatos = generar_combinaciones_candidatas(frecuencias, pares, trios, 1000)

    resultados = []
    for comb in candidatos:
        puntuacion, detalle = calcular_puntuacion_combinacion(
            comb, frecuencias, frecuencias_recientes, pares, trios,
            consecutivos_dias, pares_consecutivos,
            dia_semana_actual, frecuencias_por_dia
        )

        explicacion = generar_explicacion(comb, detalle, frecuencias, pares, trios, consecutivos_dias)

        pares_en_comb = [(p, pares.get(p, 0)) for p in combinations(comb, 2) if pares.get(p, 0) > 0]
        pares_en_comb.sort(key=lambda x: x[1], reverse=True)
        trios_en_comb = [(t, trios.get(t, 0)) for t in combinations(comb, 3) if trios.get(t, 0) > 0]
        trios_en_comb.sort(key=lambda x: x[1], reverse=True)

        freq_nums = {n: int(frecuencias[n]) for n in comb}

        resultados.append(CombinacionEstadistica(
            numeros=comb,
            puntuacion_total=puntuacion,
            detalle_puntuaciones=detalle,
            explicacion=explicacion,
            frecuencia_numeros=freq_nums,
            parejas_en_combinacion=pares_en_comb[:5],
            trios_en_combinacion=trios_en_comb[:3]
        ))

    resultados.sort(key=lambda x: x.puntuacion_total, reverse=True)
    return resultados[:5]


def generar_explicacion(
    combinacion: List[int],
    detalle: Dict[str, float],
    frecuencias: pd.Series,
    pares: Dict[Tuple[int, int], int],
    trios: Dict[Tuple[int, int, int], int],
    consecutivos_dias: Dict[int, int]
) -> str:
    """Genera una explicación legible de por qué se seleccionó la combinación."""
    partes = []

    nums_freq = [(n, frecuencias[n]) for n in combinacion]
    nums_freq.sort(key=lambda x: x[1], reverse=True)
    top_nums = [f"{n} ({f} veces)" for n, f in nums_freq[:3] if f > 0]
    if top_nums:
        partes.append(f"Números frecuentes: {', '.join(top_nums)}")

    pares_comb = [(p, pares.get(p, 0)) for p in combinations(combinacion, 2) if pares.get(p, 0) > 0]
    pares_comb.sort(key=lambda x: x[1], reverse=True)
    if pares_comb:
        top_pares = [f"{p[0]}-{p[1]} ({c} veces)" for p, c in pares_comb[:2]]
        partes.append(f"Parejas fuertes: {', '.join(top_pares)}")

    trios_comb = [(t, trios.get(t, 0)) for t in combinations(combinacion, 3) if trios.get(t, 0) > 0]
    trios_comb.sort(key=lambda x: x[1], reverse=True)
    if trios_comb:
        top_trios = [f"{t[0]}-{t[1]}-{t[2]} ({c} veces)" for t, c in trios_comb[:1]]
        partes.append(f"Trío detectado: {', '.join(top_trios)}")

    nums_consec = [n for n in combinacion if consecutivos_dias.get(n, 0) > 1]
    if nums_consec:
        partes.append(f"Números con rachas consecutivas: {', '.join(map(str, nums_consec))}")

    pares_count = sum(1 for n in combinacion if n % 2 == 0)
    bajos_count = sum(1 for n in combinacion if n <= 24)
    partes.append(f"Equilibrio: {pares_count} pares / {5-pares_count} impares, {bajos_count} bajos / {5-bajos_count} altos")

    return ". ".join(partes) + "."


def analisis_completo(df: pd.DataFrame) -> Dict[str, Any]:
    """Retorna un diccionario con todos los análisis para la UI."""
    if len(df) < 5:
        return {"error": "Insuficientes datos (mínimo 5 sorteos)"}

    frecuencias = calcular_frecuencias(df)
    frecuencias_recientes = calcular_frecuencias_recientes(df, 20)
    pares_lista, trios_lista = calcular_parejas_trios(df, 50)
    consecutivos_dias = detectar_numeros_consecutivos_dias(df)
    pares_consecutivos = calcular_parejas_consecutivas_dias(df)
    frecuencias_por_dia = calcular_frecuencias_por_dia(df)
    top5 = obtener_top_5_combinaciones(df)

    return {
        "frecuencias": frecuencias.to_dict(),
        "frecuencias_recientes": frecuencias_recientes.to_dict(),
        "top_parejas": [{"pareja": f"{p[0]}-{p[1]}", "veces": c} for p, c in pares_lista[:20]],
        "top_trios": [{"trio": f"{t[0]}-{t[1]}-{t[2]}", "veces": c} for t, c in trios_lista[:20]],
        "consecutivos_dias": {n: c for n, c in consecutivos_dias.items() if c > 0},
        "pares_consecutivos": {f"{p[0]}-{p[1]}": c for p, c in pares_consecutivos.items() if c > 0},
        "frecuencias_por_dia": {dia: freq.to_dict() for dia, freq in frecuencias_por_dia.items()},
        "top_5_combinaciones": [
            {
                "numeros": c.numeros,
                "puntuacion": round(c.puntuacion_total, 2),
                "detalle_puntuaciones": {k: round(v, 2) for k, v in c.detalle_puntuaciones.items()},
                "explicacion": c.explicacion,
                "frecuencia_numeros": c.frecuencia_numeros,
                "parejas": [{"pareja": f"{p[0]}-{p[1]}", "veces": v} for p, v in c.parejas_en_combinacion],
                "trios": [{"trio": f"{t[0]}-{t[1]}-{t[2]}", "veces": v} for t, v in c.trios_en_combinacion]
            }
            for c in top5
        ],
        "total_sorteos": len(df),
        "fecha_ultimo": df.iloc[0]["fecha"] if len(df) > 0 else None,
        "fecha_primero": df.iloc[-1]["fecha"] if len(df) > 0 else None
    }