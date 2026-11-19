"""
MÓDULO DE IMPORTACIÓN MULTI-FORMATO
====================================
Analizador Inteligente 1-49 v0.3

Soporta: PDF, TXT, DOCX, XLSX, CSV
- Detección flexible de números y fechas
- Validación estricta (1-49, sin duplicados, complementario distinto)
- Vista previa editable
- Guardado de archivos originales
- Fusión con datos existentes (solo elimina duplicados exactos)
"""

import re
import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import pdfplumber
from docx import Document


# ==========================================
# CONFIGURACIÓN Y CONSTANTES
# ==========================================

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
ARCHIVOS_ORIGINALES = DATOS / "archivos_originales"
ARCHIVO_SORTEOS = DATOS / "sorteos.csv"

COLUMNAS = [
    "fecha", "n1", "n2", "n3", "n4", "n5",
    "complementario", "archivo_origen", "fecha_importacion"
]

NUM_MIN, NUM_MAX = 1, 49

# Patrones regex para detectar números
PATRON_NUMEROS = re.compile(r'\b([1-9]|[1-3]\d|4[0-9])\b')
PATRON_FECHA_ISO = re.compile(r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b')
PATRON_FECHA_DDMM = re.compile(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b')
PATRON_FECHA_ES = re.compile(
    r'\b(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})\b', re.IGNORECASE
)


class EstadoValidacion(Enum):
    """Estados posibles de validación de un sorteo detectado."""
    VALIDO = "✅ Válido"
    PENDIENTE = "⚠️ Pendiente de revisión"
    ERROR = "❌ Error"


@dataclass
class SorteoDetectado:
    """Representa un sorteo detectado en un archivo."""
    fecha: Optional[str] = None
    numeros: List[int] = field(default_factory=list)  # 5 principales
    complementario: Optional[int] = None
    archivo_origen: str = ""
    fila_origen: Any = None  # Para referencia (número de fila, página, etc.)
    estado: EstadoValidacion = EstadoValidacion.PENDIENTE
    mensaje_validacion: str = ""
    indice_original: int = -1  # Índice en la lista original de detecciones

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para DataFrame/CSV."""
        base = {
            "fecha": self.fecha or "",
            "n1": self.numeros[0] if len(self.numeros) > 0 else "",
            "n2": self.numeros[1] if len(self.numeros) > 1 else "",
            "n3": self.numeros[2] if len(self.numeros) > 2 else "",
            "n4": self.numeros[3] if len(self.numeros) > 3 else "",
            "n5": self.numeros[4] if len(self.numeros) > 4 else "",
            "complementario": self.complementario or "",
            "archivo_origen": self.archivo_origen,
            "fecha_importacion": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return base

    @property
    def principales_ordenados(self) -> List[int]:
        """Retorna los 5 números principales ordenados."""
        return sorted(self.numeros[:5])

    @property
    def es_completo(self) -> bool:
        """Verifica si tiene los 6 números (5 + complementario)."""
        return len(self.numeros) >= 5 and self.complementario is not None

    @property
    def clave_unica(self) -> Tuple:
        """Clave única para detectar duplicados exactos (fecha + 6 números)."""
        nums = tuple(sorted(self.numeros[:5]))
        return (self.fecha, nums, self.complementario)


# ==========================================
# FUNCIONES DE LECTURA POR FORMATO
# ==========================================

def leer_pdf(ruta: Path) -> List[Dict[str, Any]]:
    """
    Extrae texto de PDF página por página.
    Retorna lista de dicts con 'texto', 'pagina'.
    """
    resultados = []
    try:
        with pdfplumber.open(ruta) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text() or ""
                if texto.strip():
                    resultados.append({
                        "texto": texto,
                        "pagina": i + 1,
                        "tipo": "pagina"
                    })
                # También intentar extraer tablas
                tablas = pagina.extract_tables()
                for j, tabla in enumerate(tablas):
                    if tabla:
                        resultados.append({
                            "texto": tabla,
                            "pagina": i + 1,
                            "tipo": "tabla",
                            "tabla_idx": j
                        })
    except Exception as e:
        raise RuntimeError(f"Error leyendo PDF: {e}")
    return resultados


def leer_txt(ruta: Path) -> List[Dict[str, Any]]:
    """
    Lee archivo TXT con codificación UTF-8 o Windows-1252.
    Retorna lista de dicts con 'texto', 'linea'.
    """
    # Probar UTF-8 primero
    for encoding in ["utf-8", "utf-8-sig", "windows-1252", "latin-1"]:
        try:
            contenido = ruta.read_text(encoding=encoding)
            lineas = contenido.splitlines()
            resultados = []
            for i, linea in enumerate(lineas):
                if linea.strip():
                    resultados.append({
                        "texto": linea,
                        "linea": i + 1,
                        "tipo": "linea"
                    })
            return resultados
        except UnicodeDecodeError:
            continue
    raise RuntimeError("No se pudo decodificar el archivo TXT")


def leer_docx(ruta: Path) -> List[Dict[str, Any]]:
    """
    Extrae texto de párrafos y tablas de Word.
    Retorna lista de dicts con 'texto', 'origen'.
    """
    resultados = []
    try:
        doc = Document(ruta)
        # Párrafos
        for i, parrafo in enumerate(doc.paragraphs):
            if parrafo.text.strip():
                resultados.append({
                    "texto": parrafo.text,
                    "origen": f"párrafo {i + 1}",
                    "tipo": "parrafo"
                })
        # Tablas
        for t_idx, tabla in enumerate(doc.tables):
            for r_idx, fila in enumerate(tabla.rows):
                celdas = [c.text for c in fila.cells]
                texto_fila = " | ".join(celdas)
                if any(c.strip() for c in celdas):
                    resultados.append({
                        "texto": texto_fila,
                        "origen": f"tabla {t_idx + 1}, fila {r_idx + 1}",
                        "tipo": "tabla",
                        "celdas": celdas
                    })
    except Exception as e:
        raise RuntimeError(f"Error leyendo DOCX: {e}")
    return resultados


def leer_excel(ruta: Path) -> List[Dict[str, Any]]:
    """
    Lee Excel (.xlsx) hoja por hoja.
    Retorna lista de dicts con 'texto' (fila como string), 'hoja', 'fila'.
    """
    resultados = []
    try:
        xls = pd.ExcelFile(ruta, engine="openpyxl")
        for hoja in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=hoja, header=None, dtype=str)
            for idx, fila in df.iterrows():
                vals = [str(v).strip() for v in fila if pd.notna(v)]
                if vals:
                    texto = " | ".join(vals)
                    resultados.append({
                        "texto": texto,
                        "hoja": hoja,
                        "fila": idx + 1,
                        "tipo": "fila",
                        "valores": vals
                    })
    except Exception as e:
        raise RuntimeError(f"Error leyendo Excel: {e}")
    return resultados


def leer_csv(ruta: Path) -> List[Dict[str, Any]]:
    """
    Lee CSV con detección automática de separador.
    Retorna lista de dicts con 'texto', 'fila', 'valores'.
    """
    resultados = []
    try:
        # Detectar separador
        with open(ruta, "r", encoding="utf-8-sig") as f:
            muestra = f.read(2048)
            f.seek(0)
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(muestra)
                separador = dialect.delimiter
            except Exception:
                separador = ","

        df = pd.read_csv(ruta, sep=separador, dtype=str, encoding="utf-8-sig")
        for idx, fila in df.iterrows():
            vals = [str(v).strip() for v in fila if pd.notna(v)]
            if vals:
                texto = " | ".join(vals)
                resultados.append({
                    "texto": texto,
                    "fila": idx + 1,
                    "tipo": "fila",
                    "valores": vals
                })
    except Exception as e:
        raise RuntimeError(f"Error leyendo CSV: {e}")
    return resultados


DISPATCH_LECTURA = {
    ".pdf": leer_pdf,
    ".txt": leer_txt,
    ".docx": leer_docx,
    ".xlsx": leer_excel,
    ".csv": leer_csv,
}


# ==========================================
# DETECCIÓN DE FECHAS Y NÚMEROS
# ==========================================

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4,
    "may": 5, "jun": 6, "jul": 7, "ago": 8,
    "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

def parsear_fecha(texto: str) -> Optional[str]:
    """
    Intenta extraer y normalizar una fecha del texto.
    Retorna fecha en formato ISO YYYY-MM-DD o None.
    """
    # 1. ISO: YYYY-MM-DD o YYYY/MM/DD
    m = PATRON_FECHA_ISO.search(texto)
    if m:
        try:
            f = m.group(1).replace("/", "-")
            dt = datetime.strptime(f, "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # 2. DD-MM-YYYY, DD/MM/YYYY, DD-MM-YY, etc.
    m = PATRON_FECHA_DDMM.search(texto)
    if m:
        f = m.group(1).replace("/", "-")
        partes = f.split("-")
        if len(partes) == 3:
            try:
                d, m, a = partes
                if len(a) == 2:
                    a = "20" + a
                dt = datetime(int(a), int(m), int(d))
                return dt.strftime("%Y-%m-%d")
            except Exception:
                pass

    # 3. Formato español: "15 de enero de 2024"
    m = PATRON_FECHA_ES.search(texto)
    if m:
        try:
            partes = m.group(1).lower().split(" de ")
            if len(partes) == 3:
                d = int(partes[0])
                mes_str = partes[1]
                a = int(partes[2])
                mes = MESES_ES.get(mes_str[:3])
                if mes:
                    dt = datetime(a, mes, d)
                    return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


def extraer_numeros_validos(texto: str) -> List[int]:
    """
    Extrae todos los números entre 1 y 49 del texto.
    Retorna lista única ordenada de aparición.
    """
    numeros = []
    for m in PATRON_NUMEROS.finditer(texto):
        n = int(m.group(1))
        if NUM_MIN <= n <= NUM_MAX:
            numeros.append(n)
    # Eliminar duplicados preservando orden
    vistos = set()
    unicos = []
    for n in numeros:
        if n not in vistos:
            vistos.add(n)
            unicos.append(n)
    return unicos


def detectar_sorteos_en_texto(
    texto: str,
    archivo_origen: str,
    referencia: Any
) -> List[SorteoDetectado]:
    """
    Intenta detectar uno o más sorteos en un bloque de texto.
    Estrategia:
    1. Busca fecha
    2. Busca números 1-49
    3. Agrupa en bloques de 6 números (5 + complementario)
    """
    sorteos = []

    # Extraer fecha si hay
    fecha = parsear_fecha(texto)

    # Remover la fecha del texto para no detectar sus números
    texto_sin_fecha = texto
    if fecha:
        texto_sin_fecha = PATRON_FECHA_ISO.sub("", texto_sin_fecha)
        texto_sin_fecha = PATRON_FECHA_DDMM.sub("", texto_sin_fecha)
        texto_sin_fecha = PATRON_FECHA_ES.sub("", texto_sin_fecha)

    # Extraer números válidos del texto sin fecha
    numeros = extraer_numeros_validos(texto_sin_fecha)

    # Necesitamos al menos 6 números para un sorteo completo
    if len(numeros) < 6:
        # No hay suficientes números, marcar como pendiente
        s = SorteoDetectado(
            fecha=fecha,
            numeros=numeros[:5],
            complementario=numeros[5] if len(numeros) > 5 else None,
            archivo_origen=archivo_origen,
            fila_origen=referencia,
            estado=EstadoValidacion.PENDIENTE,
            mensaje_validacion=f"Solo {len(numeros)} números detectados (mínimo 6)"
        )
        if numeros:
            sorteos.append(s)
        return sorteos

    # Si hay 6 o más, intentar agrupar en sorteos de 6 números
    # Estrategia: ventana deslizante de 6, o bloques consecutivos
    i = 0
    while i + 5 < len(numeros):
        bloque = numeros[i:i+6]
        # Verificar que los 5 primeros son únicos
        principales = bloque[:5]
        comp = bloque[5]

        if len(set(principales)) == 5 and comp not in principales:
            s = SorteoDetectado(
                fecha=fecha,
                numeros=principales,
                complementario=comp,
                archivo_origen=archivo_origen,
                fila_origen=referencia,
                estado=EstadoValidacion.VALIDO,
                mensaje_validacion="Detectado automáticamente"
            )
            sorteos.append(s)
            i += 6  # Avanzar al siguiente bloque
        else:
            # No es un sorteo válido, avanzar 1 y reintentar
            i += 1

    # Si no se detectó ninguno válido pero hay números, crear pendiente
    if not sorteos and numeros:
        s = SorteoDetectado(
            fecha=fecha,
            numeros=numeros[:5],
            complementario=numeros[5] if len(numeros) > 5 else None,
            archivo_origen=archivo_origen,
            fila_origen=referencia,
            estado=EstadoValidacion.PENDIENTE,
            mensaje_validacion="Números detectados pero estructura no clara"
        )
        sorteos.append(s)

    return sorteos


def detectar_sorteos_en_tabla(
    celdas: List[str],
    archivo_origen: str,
    referencia: Any
) -> List[SorteoDetectado]:
    """
    Detecta sorteos en una fila de tabla (lista de celdas).
    Intenta identificar columnas de fecha y números.
    """
    sorteos = []
    texto_completo = " | ".join(celdas)

    # Extraer fecha
    fecha = parsear_fecha(texto_completo)

    # Remover la fecha del texto para no detectar sus números
    texto_sin_fecha = texto_completo
    if fecha:
        # Remover patrones de fecha comunes
        texto_sin_fecha = PATRON_FECHA_ISO.sub("", texto_sin_fecha)
        texto_sin_fecha = PATRON_FECHA_DDMM.sub("", texto_sin_fecha)
        texto_sin_fecha = PATRON_FECHA_ES.sub("", texto_sin_fecha)

    # Extraer números del texto sin fecha
    numeros = extraer_numeros_validos(texto_sin_fecha)

    if len(numeros) >= 6:
        # Intentar detectar estructura: 5 principales + complementario
        # Buscar patrones comunes: última columna = complementario
        # o columna marcada como "complementario"
        principales = numeros[:5]
        comp = numeros[5]

        if len(set(principales)) == 5 and comp not in principales:
            s = SorteoDetectado(
                fecha=fecha,
                numeros=principales,
                complementario=comp,
                archivo_origen=archivo_origen,
                fila_origen=referencia,
                estado=EstadoValidacion.VALIDO,
                mensaje_validacion="Detectado en tabla"
            )
            sorteos.append(s)
        else:
            s = SorteoDetectado(
                fecha=fecha,
                numeros=principales,
                complementario=comp if comp not in principales else None,
                archivo_origen=archivo_origen,
                fila_origen=referencia,
                estado=EstadoValidacion.PENDIENTE,
                mensaje_validacion="Estructura de tabla no estándar"
            )
            sorteos.append(s)
    elif numeros:
        s = SorteoDetectado(
            fecha=fecha,
            numeros=numeros[:5],
            complementario=numeros[5] if len(numeros) > 5 else None,
            archivo_origen=archivo_origen,
            fila_origen=referencia,
            estado=EstadoValidacion.PENDIENTE,
            mensaje_validacion=f"Solo {len(numeros)} números en fila de tabla"
        )
        sorteos.append(s)

    return sorteos


# ==========================================
# PROCESADOR PRINCIPAL
# ==========================================

def procesar_archivo(ruta: Path) -> List[SorteoDetectado]:
    """
    Procesa un archivo según su extensión y detecta todos los sorteos.
    Retorna lista de SorteoDetectado.
    """
    extension = ruta.suffix.lower()
    if extension not in DISPATCH_LECTURA:
        raise ValueError(f"Formato no soportado: {extension}")

    leer = DISPATCH_LECTURA[extension]
    bloques = leer(ruta)

    todos_sorteos = []
    for idx, bloque in enumerate(bloques):
        texto = bloque.get("texto", "")
        ref = bloque.get("pagina") or bloque.get("linea") or bloque.get("fila") or bloque.get("origen") or idx

        if isinstance(texto, list):  # Tabla de pdfplumber
            # Convertir tabla a filas
            for f_idx, fila in enumerate(texto):
                if fila:
                    celdas = [str(c).strip() for c in fila if c is not None]
                    if any(celdas):
                        sorteos = detectar_sorteos_en_tabla(
                            celdas, ruta.name, f"{ref} - fila {f_idx + 1}"
                        )
                        todos_sorteos.extend(sorteos)
        elif bloque.get("tipo") == "tabla" and "celdas" in bloque:
            sorteos = detectar_sorteos_en_tabla(
                bloque["celdas"], ruta.name, bloque.get("origen", ref)
            )
            todos_sorteos.extend(sorteos)
        elif bloque.get("tipo") == "fila" and "valores" in bloque:
            # CSV y Excel: procesar cada fila como tabla
            celdas = bloque["valores"]
            if any(celdas):
                sorteos = detectar_sorteos_en_tabla(
                    celdas, ruta.name, bloque.get("fila", ref)
                )
                todos_sorteos.extend(sorteos)
        elif isinstance(texto, str) and texto.strip():
            sorteos = detectar_sorteos_en_texto(
                texto, ruta.name, ref
            )
            todos_sorteos.extend(sorteos)

    # Asignar índices originales
    for i, s in enumerate(todos_sorteos):
        s.indice_original = i

    return todos_sorteos


def procesar_multiples_archivos(rutas: List[Path]) -> List[SorteoDetectado]:
    """
    Procesa múltiples archivos y combina resultados.
    """
    todos = []
    for ruta in rutas:
        try:
            sorteos = procesar_archivo(ruta)
            todos.extend(sorteos)
        except Exception as e:
            # Agregar entrada de error
            s = SorteoDetectado(
                archivo_origen=ruta.name,
                fila_origen="ERROR",
                estado=EstadoValidacion.ERROR,
                mensaje_validacion=str(e)
            )
            todos.append(s)
    return todos


# ==========================================
# VALIDACIÓN
# ==========================================

def validar_sorteo(s: SorteoDetectado) -> Tuple[bool, str]:
    """
    Valida un sorteo detectado.
    Retorna (es_valido, mensaje).
    """
    # Verificar 5 principales
    if len(s.numeros) < 5:
        return False, "Faltan números principales (necesarios 5)"

    principales = s.numeros[:5]

    # Rango 1-49
    for n in principales:
        if n < NUM_MIN or n > NUM_MAX:
            return False, f"Número {n} fuera de rango (1-49)"

    # Sin duplicados en principales
    if len(set(principales)) != 5:
        return False, "Números principales duplicados"

    # Complementario
    if s.complementario is None:
        return False, "Falta número complementario"

    if s.complementario < NUM_MIN or s.complementario > NUM_MAX:
        return False, f"Complementario {s.complementario} fuera de rango (1-49)"

    if s.complementario in principales:
        return False, "Complementario coincide con un principal"

    # Fecha (opcional pero recomendada)
    if not s.fecha:
        return True, "Válido (sin fecha)"

    # Validar formato fecha
    try:
        datetime.strptime(s.fecha, "%Y-%m-%d")
    except Exception:
        return False, f"Formato de fecha inválido: {s.fecha}"

    return True, "Válido"


def validar_todos(sorteos: List[SorteoDetectado]) -> List[SorteoDetectado]:
    """
    Valida lista de sorteos y actualiza su estado.
    """
    for s in sorteos:
        if s.estado == EstadoValidacion.ERROR:
            continue
        es_valido, msg = validar_sorteo(s)
        s.estado = EstadoValidacion.VALIDO if es_valido else EstadoValidacion.PENDIENTE
        s.mensaje_validacion = msg
    return sorteos


# ==========================================
# GUARDADO DE ARCHIVOS ORIGINALES
# ==========================================

def guardar_archivo_original(ruta_origen: Path) -> Path:
    """
    Copia el archivo original a la carpeta de archivos_originales
    con timestamp para evitar colisiones.
    Retorna la ruta destino.
    """
    ARCHIVOS_ORIGINALES.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_base = ruta_origen.stem
    extension = ruta_origen.suffix
    nombre_destino = f"{timestamp}_{nombre_base}{extension}"
    ruta_destino = ARCHIVOS_ORIGINALES / nombre_destino

    # Si ya existe, añadir contador
    contador = 1
    while ruta_destino.exists():
        nombre_destino = f"{timestamp}_{nombre_base}_{contador}{extension}"
        ruta_destino = ARCHIVOS_ORIGINALES / nombre_destino
        contador += 1

    # Copiar archivo
    ruta_destino.write_bytes(ruta_origen.read_bytes())
    return ruta_destino


# ==========================================
# FUSIÓN CON DATOS EXISTENTES
# ==========================================

def cargar_sorteos_existentes() -> pd.DataFrame:
    """Carga el CSV de sorteos existente."""
    if not ARCHIVO_SORTEOS.exists():
        return pd.DataFrame(columns=COLUMNAS)

    try:
        df = pd.read_csv(ARCHIVO_SORTEOS, dtype=str)
        # Asegurar todas las columnas
        for c in COLUMNAS:
            if c not in df.columns:
                df[c] = ""
        return df[COLUMNAS]
    except Exception:
        return pd.DataFrame(columns=COLUMNAS)


def obtener_claves_existentes(df: pd.DataFrame) -> set:
    """Obtiene conjunto de claves únicas de sorteos existentes."""
    claves = set()
    for _, fila in df.iterrows():
        try:
            fecha = str(fila.get("fecha", "")).strip()
            n1 = int(fila.get("n1", 0))
            n2 = int(fila.get("n2", 0))
            n3 = int(fila.get("n3", 0))
            n4 = int(fila.get("n4", 0))
            n5 = int(fila.get("n5", 0))
            comp = int(fila.get("complementario", 0))
            if all(v > 0 for v in [n1, n2, n3, n4, n5, comp]):
                nums = tuple(sorted([n1, n2, n3, n4, n5]))
                claves.add((fecha, nums, comp))
        except Exception:
            continue
    return claves


def fusionar_sorteos(
    sorteos_nuevos: List[SorteoDetectado],
    df_existente: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Fusiona sorteos nuevos con existentes.
    Elimina solo duplicados exactos (fecha + 6 números).
    Retorna (DataFrame fusionado, estadísticas).
    """
    claves_existentes = obtener_claves_existentes(df_existente)

    stats = {
        "nuevos_agregados": 0,
        "duplicados_omitidos": 0,
        "con_error": 0,
        "pendientes": 0
    }

    filas_nuevas = []

    for s in sorteos_nuevos:
        if s.estado == EstadoValidacion.ERROR:
            stats["con_error"] += 1
            continue

        if s.estado == EstadoValidacion.PENDIENTE:
            stats["pendientes"] += 1

        # Solo agregar los válidos
        if s.estado == EstadoValidacion.VALIDO:
            clave = s.clave_unica
            if clave in claves_existentes:
                stats["duplicados_omitidos"] += 1
                continue

            filas_nuevas.append(s.to_dict())
            claves_existentes.add(clave)
            stats["nuevos_agregados"] += 1

    if filas_nuevas:
        df_nuevos = pd.DataFrame(filas_nuevas, columns=COLUMNAS)
        df_fusionado = pd.concat([df_existente, df_nuevos], ignore_index=True)
    else:
        df_fusionado = df_existente.copy()

    # Ordenar por fecha (más recientes primero)
    if "fecha" in df_fusionado.columns:
        df_fusionado["_fecha_sort"] = pd.to_datetime(
            df_fusionado["fecha"], errors="coerce"
        )
        df_fusionado = df_fusionado.sort_values(
            "_fecha_sort", ascending=False, na_position="last"
        ).drop(columns=["_fecha_sort"])

    return df_fusionado, stats


def guardar_sorteos(df: pd.DataFrame) -> None:
    """Guarda DataFrame en CSV con encoding utf-8-sig."""
    df.to_csv(ARCHIVO_SORTEOS, index=False, encoding="utf-8-sig")


# ==========================================
# FUNCIÓN PRINCIPAL DE ALTO NIVEL
# ==========================================

def importar_archivos(rutas: List[Path]) -> Dict[str, Any]:
    """
    Pipeline completo de importación:
    1. Guarda archivos originales
    2. Procesa y detecta sorteos
    3. Valida
    4. Fusiona con existentes
    5. Guarda
    Retorna diccionario con resultados y estadísticas.
    """
    resultados = {
        "archivos_procesados": [],
        "sorteos_detectados": [],
        "sorteos_validos": [],
        "sorteos_pendientes": [],
        "sorteos_error": [],
        "estadisticas_fusion": {},
        "df_final": None,
        "errores": []
    }

    # 1. Guardar archivos originales
    for ruta in rutas:
        try:
            destino = guardar_archivo_original(ruta)
            resultados["archivos_procesados"].append({
                "original": ruta.name,
                "guardado_como": destino.name,
                "ruta": str(destino)
            })
        except Exception as e:
            resultados["errores"].append(f"Error guardando {ruta.name}: {e}")

    # 2. Procesar archivos
    todos_detectados = procesar_multiples_archivos(rutas)
    resultados["sorteos_detectados"] = todos_detectados

    # 3. Validar
    validar_todos(todos_detectados)

    # Separar por estado
    for s in todos_detectados:
        if s.estado == EstadoValidacion.VALIDO:
            resultados["sorteos_validos"].append(s)
        elif s.estado == EstadoValidacion.PENDIENTE:
            resultados["sorteos_pendientes"].append(s)
        elif s.estado == EstadoValidacion.ERROR:
            resultados["sorteos_error"].append(s)

    # 4. Cargar existentes y fusionar
    df_existente = cargar_sorteos_existentes()
    df_fusionado, stats = fusionar_sorteos(todos_detectados, df_existente)
    resultados["estadisticas_fusion"] = stats
    resultados["df_final"] = df_fusionado

    # 5. Guardar
    try:
        guardar_sorteos(df_fusionado)
    except Exception as e:
        resultados["errores"].append(f"Error guardando CSV: {e}")

    return resultados


# ==========================================
# UTILIDADES PARA UI (STREAMLIT)
# ==========================================

def sorteos_a_dataframe(sorteos: List[SorteoDetectado]) -> pd.DataFrame:
    """Convierte lista de sorteos a DataFrame para vista previa."""
    filas = []
    for s in sorteos:
        fila = s.to_dict()
        fila["estado"] = s.estado.value
        fila["validacion"] = s.mensaje_validacion
        fila["referencia"] = str(s.fila_origen) if s.fila_origen else ""
        filas.append(fila)
    return pd.DataFrame(filas)


def aplicar_correcciones(
    sorteos: List[SorteoDetectado],
    correcciones: Dict[int, Dict[str, Any]]
) -> List[SorteoDetectado]:
    """
    Aplica correcciones manuales a sorteos.
    correcciones: {indice_original: {campo: valor}}
    """
    for idx, cambios in correcciones.items():
        if 0 <= idx < len(sorteos):
            s = sorteos[idx]
            if "fecha" in cambios:
                s.fecha = cambios["fecha"] or None
            if "numeros" in cambios:
                s.numeros = cambios["numeros"]
            if "complementario" in cambios:
                s.complementario = cambios["complementario"]
            # Re-validar
            es_valido, msg = validar_sorteo(s)
            s.estado = EstadoValidacion.VALIDO if es_valido else EstadoValidacion.PENDIENTE
            s.mensaje_validacion = msg
    return sorteos