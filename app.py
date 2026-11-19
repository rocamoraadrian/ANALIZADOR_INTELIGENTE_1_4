
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from itertools import combinations
from collections import Counter
import tempfile
import os
from datetime import datetime

# Importar módulo de importación
from importador import (
    importar_archivos,
    sorteos_a_dataframe,
    aplicar_correcciones,
    EstadoValidacion,
    SorteoDetectado,
    ARCHIVO_SORTEOS,
    COLUMNAS as COLUMNAS_IMPORTADOR
)

# Importar módulo de estadísticas avanzadas
from estadisticas_avanzadas import analisis_completo, CombinacionEstadistica

# ==========================================
# CONFIGURACIÓN Y ALMACENAMIENTO EN EL USB
# ==========================================

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
INFORMES = BASE / "informes"

DATOS.mkdir(exist_ok=True)
INFORMES.mkdir(exist_ok=True)

ARCHIVO = DATOS / "sorteos.csv"

# Asegurar que COLUMNAS sea consistente
COLUMNAS = COLUMNAS_IMPORTADOR

st.set_page_config(
    page_title="Analizador Inteligente 1-49",
    page_icon="🔢",
    layout="wide"
)

# ==========================================
# DISEÑO
# ==========================================

st.markdown("""
<style>
.stApp {
    background-color: #101522;
}
[data-testid="stMetric"] {
    background-color: #1c293b;
    padding: 16px;
    border-radius: 12px;
}
h1, h2, h3 {
    color: #65b5ff;
}
</style>
""", unsafe_allow_html=True)

st.title("🔢 ANALIZADOR INTELIGENTE 1-49")
st.caption("Motor de análisis estadístico | Datos guardados en USB")

# ==========================================
# GENERACIÓN DE DATOS FICTICIOS
# ==========================================

def generar_datos_prueba(cantidad=200):
    rng = np.random.default_rng(149)
    filas = []

    fechas = pd.date_range(
        end=pd.Timestamp.today().normalize(),
        periods=cantidad,
        freq="D"
    )

    for fecha in fechas:
        principales = sorted(
            rng.choice(np.arange(1, 50), 5, replace=False).tolist()
        )

        disponibles = [
            n for n in range(1, 50)
            if n not in principales
        ]

        complementario = int(rng.choice(disponibles))

        filas.append({
            "fecha": fecha.strftime("%Y-%m-%d"),
            "n1": principales[0],
            "n2": principales[1],
            "n3": principales[2],
            "n4": principales[3],
            "n5": principales[4],
            "complementario": complementario
        })

    return pd.DataFrame(filas, columns=COLUMNAS)


# ==========================================
# CARGAR Y VALIDAR RESULTADOS
# ==========================================

def cargar_datos():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)

    try:
        df = pd.read_csv(ARCHIVO)

        if not all(c in df.columns for c in COLUMNAS):
            st.error("El archivo de resultados tiene un formato incorrecto.")
            return pd.DataFrame(columns=COLUMNAS)

        return df[COLUMNAS]

    except Exception as error:
        st.error(f"No se pudieron cargar los resultados: {error}")
        return pd.DataFrame(columns=COLUMNAS)


def validar_datos(df):
    if df.empty:
        return False

    try:
        numeros = df[["n1", "n2", "n3", "n4", "n5",
                      "complementario"]].astype(int)

        for _, fila in numeros.iterrows():
            principales = fila.iloc[:5].tolist()
            complementario = fila.iloc[5]

            if any(n < 1 or n > 49 for n in principales):
                return False

            if len(set(principales)) != 5:
                return False

            if complementario < 1 or complementario > 49:
                return False

            if complementario in principales:
                return False

        return True

    except Exception:
        return False


def guardar_datos(df):
    df.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")


df = cargar_datos()

# ==========================================
# MENÚ
# ==========================================

seccion = st.sidebar.radio(
    "MENÚ PRINCIPAL",
    [
        "Inicio",
        "Importar archivos",
        "Datos de prueba",
        "Análisis estadístico",
        "Parejas y tríos",
        "Números atrasados",
        "Generador 5 + 1",
        "TOP 5 Combinaciones Estadísticas",
        "Comprobar resultado",
        "Historial"
    ]
)

st.sidebar.divider()
st.sidebar.write("📁 Almacenamiento")
st.sidebar.caption(str(DATOS))
st.sidebar.caption(f"Resultados guardados: {len(df)}")

# ==========================================
# INICIO
# ==========================================

if seccion == "Inicio":

    st.header("Panel de control")

    c1, c2, c3 = st.columns(3)

    c1.metric("Sorteos guardados", len(df))
    c2.metric("Números principales", 49)
    c3.metric("Formato", "5 + 1")

    st.divider()

    st.subheader("Estado del analizador")

    if len(df) > 0 and validar_datos(df):
        st.success("Los resultados guardados son válidos.")
    else:
        st.warning("Todavía no hay resultados válidos. Genera los datos de prueba.")

    st.write("""
    Desde este panel podrás estudiar:

    - Frecuencias de aparición.
    - Números más y menos frecuentes.
    - Parejas y tríos repetidos.
    - Números que llevan más sorteos sin aparecer.
    - Combinaciones de cinco números y complementario.
    - Comprobación de nuevos resultados.
    """)

# ==========================================
# IMPORTAR ARCHIVOS
# ==========================================

elif seccion == "Importar archivos":

    st.header("📥 Importar resultados desde archivos")
    st.caption("Formatos: PDF, TXT, Word (.docx), Excel (.xlsx), CSV")

    st.write("""
    Sube uno o varios archivos con resultados históricos.
    El sistema detectará automáticamente fechas, los 5 números principales
    y el complementario. Podrás revisar y corregir antes de importar.
    """)

    # Inicializar estado de sesión para importación
    if "importacion_sorteos" not in st.session_state:
        st.session_state.importacion_sorteos = []
    if "importacion_archivos_info" not in st.session_state:
        st.session_state.importacion_archivos_info = []
    if "importacion_paso" not in st.session_state:
        st.session_state.importacion_paso = "subida"  # subida, vista_previa, confirmado

    # ---- PASO 1: SUBIDA DE ARCHIVOS ----
    if st.session_state.importacion_paso == "subida":

        archivos_subidos = st.file_uploader(
            "Selecciona archivos",
            type=["pdf", "txt", "docx", "xlsx", "csv"],
            accept_multiple_files=True,
            help="Puedes seleccionar varios archivos a la vez"
        )

        if archivos_subidos:
            st.write(f"📎 {len(archivos_subidos)} archivo(s) seleccionado(s):")
            for a in archivos_subidos:
                st.caption(f"• {a.name} ({a.size:,} bytes)")

            if st.button("🔍 Analizar y detectar sorteos", type="primary"):
                # Guardar archivos temporales para procesamiento
                rutas_temporales = []
                for archivo in archivos_subidos:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=Path(archivo.name).suffix
                    ) as tmp:
                        tmp.write(archivo.getvalue())
                        rutas_temporales.append(Path(tmp.name))

                # Procesar con el importador
                with st.spinner("Analizando archivos..."):
                    resultado = importar_archivos(rutas_temporales)

                # Limpiar temporales
                for r in rutas_temporales:
                    try:
                        r.unlink()
                    except Exception:
                        pass

                # Guardar en sesión
                st.session_state.importacion_sorteos = resultado["sorteos_detectados"]
                st.session_state.importacion_archivos_info = resultado["archivos_procesados"]
                st.session_state.importacion_resultado = resultado
                st.session_state.importacion_paso = "vista_previa"
                st.rerun()

    # ---- PASO 2: VISTA PREVIA Y CORRECCIÓN ----
    elif st.session_state.importacion_paso == "vista_previa":

        sorteos = st.session_state.importacion_sorteos
        archivos_info = st.session_state.importacion_archivos_info

        if not sorteos:
            st.warning("No se detectaron sorteos en los archivos.")
            if st.button("← Volver a subir archivos"):
                st.session_state.importacion_paso = "subida"
                st.session_state.importacion_sorteos = []
                st.rerun()
        else:
            # Mostrar info de archivos procesados
            with st.expander("📄 Archivos procesados", expanded=False):
                for info in archivos_info:
                    st.caption(f"{info['original']} → guardado como {info['guardado_como']}")

            # Convertir a DataFrame para edición
            df_previa = sorteos_a_dataframe(sorteos)

            # Mostrar resumen
            validos = sum(1 for s in sorteos if s.estado == EstadoValidacion.VALIDO)
            pendientes = sum(1 for s in sorteos if s.estado == EstadoValidacion.PENDIENTE)
            errores = sum(1 for s in sorteos if s.estado == EstadoValidacion.ERROR)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total detectados", len(sorteos))
            c2.metric("✅ Válidos", validos)
            c3.metric("⚠️ Pendientes", pendientes)
            c4.metric("❌ Errores", errores)

            st.divider()

            st.subheader("📋 Vista previa - Edita si es necesario")

            # Editor de datos
            column_config = {
                "fecha": st.column_config.TextColumn("Fecha (YYYY-MM-DD)", width="small"),
                "n1": st.column_config.NumberColumn("N1", min_value=1, max_value=49, width="small"),
                "n2": st.column_config.NumberColumn("N2", min_value=1, max_value=49, width="small"),
                "n3": st.column_config.NumberColumn("N3", min_value=1, max_value=49, width="small"),
                "n4": st.column_config.NumberColumn("N4", min_value=1, max_value=49, width="small"),
                "n5": st.column_config.NumberColumn("N5", min_value=1, max_value=49, width="small"),
                "complementario": st.column_config.NumberColumn("Comp.", min_value=1, max_value=49, width="small"),
                "archivo_origen": st.column_config.TextColumn("Archivo", width="medium"),
                "estado": st.column_config.TextColumn("Estado", width="small"),
                "validacion": st.column_config.TextColumn("Validación", width="large"),
                "referencia": st.column_config.TextColumn("Ref.", width="small"),
            }

            df_editado = st.data_editor(
                df_previa,
                column_config=column_config,
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                key="editor_importacion"
            )

            st.divider()

            # Detectar cambios y aplicar correcciones
            correcciones = {}
            for idx, (orig, edit) in enumerate(zip(df_previa.to_dict("records"), df_editado.to_dict("records"))):
                cambios = {}
                # Comparar campos editables
                for campo in ["fecha", "n1", "n2", "n3", "n4", "n5", "complementario"]:
                    val_orig = orig.get(campo)
                    val_edit = edit.get(campo)
                    if val_orig != val_edit:
                        if campo == "fecha":
                            cambios["fecha"] = val_edit if val_edit else None
                        elif campo.startswith("n"):
                            # Reconstruir lista de números
                            pass
                        elif campo == "complementario":
                            cambios["complementario"] = int(val_edit) if val_edit else None

                def _safe_int(val, default=0):
                    """Convierte a int de forma segura, manejando NaN, None, strings vacíos."""
                    try:
                        if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
                            return default
                        return int(val)
                    except (ValueError, TypeError):
                        return default

                # Reconstruir números si cambiaron
                nums_nuevos = [
                    _safe_int(edit.get("n1")),
                    _safe_int(edit.get("n2")),
                    _safe_int(edit.get("n3")),
                    _safe_int(edit.get("n4")),
                    _safe_int(edit.get("n5"))
                ]
                nums_orig = [
                    _safe_int(orig.get("n1")),
                    _safe_int(orig.get("n2")),
                    _safe_int(orig.get("n3")),
                    _safe_int(orig.get("n4")),
                    _safe_int(orig.get("n5"))
                ]
                if nums_nuevos != nums_orig:
                    cambios["numeros"] = nums_nuevos

                if cambios:
                    correcciones[idx] = cambios

            if correcciones:
                st.session_state.importacion_sorteos = aplicar_correcciones(
                    st.session_state.importacion_sorteos, correcciones
                )
                st.success(f"✅ {len(correcciones)} sorteo(s) corregido(s). La vista se actualiza.")
                st.rerun()

            # Botones de acción
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                if st.button("← Volver a subir archivos"):
                    st.session_state.importacion_paso = "subida"
                    st.session_state.importacion_sorteos = []
                    st.rerun()

            with col_b:
                if st.button("🗑️ Descartar y reiniciar"):
                    st.session_state.importacion_paso = "subida"
                    st.session_state.importacion_sorteos = []
                    st.session_state.importacion_archivos_info = []
                    st.rerun()

            with col_c:
                # Solo permitir importar si hay válidos
                validos_actuales = sum(
                    1 for s in st.session_state.importacion_sorteos
                    if s.estado == EstadoValidacion.VALIDO
                )
                if validos_actuales > 0:
                    if st.button(f"💾 Importar {validos_actuales} sorteos válidos", type="primary"):
                        # Ejecutar importación final
                        with st.spinner("Guardando en USB..."):
                            resultado = st.session_state.importacion_resultado
                            # Re-ejecutar fusión con datos corregidos
                            from importador import (
                                cargar_sorteos_existentes,
                                fusionar_sorteos,
                                guardar_sorteos
                            )
                            df_existente = cargar_sorteos_existentes()
                            df_fusionado, stats = fusionar_sorteos(
                                st.session_state.importacion_sorteos, df_existente
                            )
                            guardar_sorteos(df_fusionado)

                        st.success("✅ Importación completada")
                        st.write(f"**Nuevos agregados:** {stats['nuevos_agregados']}")
                        st.write(f"**Duplicados omitidos:** {stats['duplicados_omitidos']}")
                        st.write(f"**Pendientes (no importados):** {stats['pendientes']}")
                        st.write(f"**Errores:** {stats['con_error']}")

                        # Limpiar estado
                        st.session_state.importacion_paso = "subida"
                        st.session_state.importacion_sorteos = []
                        st.session_state.importacion_archivos_info = []

                        # Recargar datos principales
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.button("💾 Importar (ningún sorteo válido)", disabled=True)
                    st.caption("Corrige los sorteos pendientes para habilitar")

# ==========================================
# DATOS DE PRUEBA
# ==========================================

elif seccion == "Datos de prueba":

    st.header("🧪 Crear datos de prueba")

    st.write(
        "Genera 200 sorteos ficticios para probar el funcionamiento "
        "del analizador."
    )

    st.info(
        "Esta operación sustituye los resultados guardados actualmente "
        "en el archivo de prueba sorteos.csv."
    )

    if st.button("Generar 200 sorteos ficticios", type="primary"):

        df = generar_datos_prueba(200)

        guardar_datos(df)

        st.success(
            "Se han generado y guardado 200 sorteos en tu USB."
        )

        st.dataframe(df.tail(10), use_container_width=True)

    if len(df) > 0:
        st.subheader("Datos actualmente guardados")
        st.write(f"Total de sorteos: {len(df)}")
        st.dataframe(df.tail(10), use_container_width=True)

# ==========================================
# PREPARAR FRECUENCIAS
# ==========================================

elif seccion in [
    "Análisis estadístico",
    "Parejas y tríos",
    "Números atrasados",
    "Generador 5 + 1",
    "TOP 5 Combinaciones Estadísticas",
    "Comprobar resultado",
    "Historial"
]:

    if not validar_datos(df):

        st.warning(
            "Primero genera los 200 sorteos de prueba "
            "desde la sección Datos de prueba."
        )

    else:

        principales = df[
            ["n1", "n2", "n3", "n4", "n5"]
        ].astype(int)

        todos = principales.to_numpy().flatten()

        frecuencias = (
            pd.Series(todos)
            .value_counts()
            .reindex(range(1, 50), fill_value=0)
        )

        frecuencia_complementario = (
            df["complementario"]
            .astype(int)
            .value_counts()
            .reindex(range(1, 50), fill_value=0)
        )

        # ==================================
        # ANÁLISIS ESTADÍSTICO
        # ==================================

        if seccion == "Análisis estadístico":

            st.header("📊 Frecuencia de los 49 números")

            ranking = pd.DataFrame({
                "Número": range(1, 50),
                "Apariciones": frecuencias.values,
                "Complementario": frecuencia_complementario.values
            })

            ranking["Porcentaje"] = (
                ranking["Apariciones"] / len(df) * 100
            ).round(2)

            ranking = ranking.sort_values(
                "Apariciones", ascending=False
            )

            a, b = st.columns(2)

            a.metric(
                "Número más frecuente",
                int(frecuencias.idxmax()),
                f"{int(frecuencias.max())} apariciones"
            )

            b.metric(
                "Número menos frecuente",
                int(frecuencias.idxmin()),
                f"{int(frecuencias.min())} apariciones"
            )

            st.subheader("Ranking de frecuencias")

            st.bar_chart(ranking.set_index("Número")["Apariciones"])

            st.dataframe(
                ranking,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("Frecuencia del complementario")

            comp = pd.DataFrame({
                "Número": range(1, 50),
                "Apariciones": frecuencia_complementario.values
            })

            st.bar_chart(comp.set_index("Número"))

            pares = sum(n % 2 == 0 for n in todos)
            impares = len(todos) - pares

            bajos = sum(n <= 24 for n in todos)
            altos = len(todos) - bajos

            x, y, z, w = st.columns(4)

            x.metric("Pares", pares)
            y.metric("Impares", impares)
            z.metric("Bajos (1-24)", bajos)
            w.metric("Altos (25-49)", altos)

        # ==================================
        # PAREJAS Y TRÍOS
        # ==================================

        elif seccion == "Parejas y tríos":

            st.header("🔎 Detector de parejas y tríos")

            contador_parejas = Counter()
            contador_trios = Counter()

            for fila in principales.to_numpy():
                numeros = sorted(map(int, fila))

                contador_parejas.update(combinations(numeros, 2))
                contador_trios.update(combinations(numeros, 3))

            def mostrar_combinaciones(contador, nombre):
                st.subheader(nombre)

                resultados = [
                    {
                        "Combinación": " - ".join(map(str, combo)),
                        "Apariciones": total
                    }
                    for combo, total in contador.most_common(20)
                ]

                st.dataframe(
                    pd.DataFrame(resultados),
                    use_container_width=True,
                    hide_index=True
                )

            mostrar_combinaciones(
                contador_parejas,
                "20 parejas más repetidas"
            )

            mostrar_combinaciones(
                contador_trios,
                "20 tríos más repetidos"
            )

        # ==================================
        # NÚMEROS ATRASADOS
        # ==================================

        elif seccion == "Números atrasados":

            st.header("⏳ Números sin aparecer")

            ultima_aparicion = {}

            for numero in range(1, 50):
                posiciones = [
                    i for i, fila in enumerate(
                        principales.to_numpy()
                    )
                    if numero in fila
                ]

                if posiciones:
                    ultima_aparicion[numero] = (
                        len(df) - 1 - max(posiciones)
                    )
                else:
                    ultima_aparicion[numero] = len(df)

            atrasos = pd.DataFrame([
                {
                    "Número": numero,
                    "Sorteos sin aparecer": retraso
                }
                for numero, retraso in ultima_aparicion.items()
            ])

            atrasos = atrasos.sort_values(
                "Sorteos sin aparecer",
                ascending=False
            )

            st.dataframe(
                atrasos,
                use_container_width=True,
                hide_index=True
            )

            st.bar_chart(
                atrasos.set_index("Número")
            )

        # ==================================
        # GENERADOR DE COMBINACIONES
        # ==================================

        elif seccion == "Generador 5 + 1":

            st.header("🎯 Generador de combinaciones")

            cantidad = st.selectbox(
                "Número de combinaciones",
                [5, 10, 20, 50]
            )

            criterio = st.selectbox(
                "Método de generación",
                [
                    "Aleatorio equilibrado",
                    "Ponderado por frecuencias históricas"
                ]
            )

            if st.button("Generar combinaciones", type="primary"):

                rng = np.random.default_rng()

                pesos = np.ones(49)

                if criterio == "Ponderado por frecuencias históricas":
                    pesos = frecuencias.to_numpy(dtype=float) + 1
                    pesos = pesos / pesos.sum()

                resultados = []

                for i in range(cantidad):

                    principales_nuevos = rng.choice(
                        np.arange(1, 50),
                        size=5,
                        replace=False,
                        p=pesos
                    )

                    principales_nuevos = sorted(
                        map(int, principales_nuevos)
                    )

                    disponibles = [
                        n for n in range(1, 50)
                        if n not in principales_nuevos
                    ]

                    pesos_comp = np.array([
                        frecuencia_complementario[n - 1] + 1
                        for n in disponibles
                    ], dtype=float)

                    pesos_comp /= pesos_comp.sum()

                    complementario = int(
                        rng.choice(disponibles, p=pesos_comp)
                    )

                    resultados.append({
                        "Combinación": i + 1,
                        "Números": " - ".join(
                            map(str, principales_nuevos)
                        ),
                        "Complementario": complementario
                    })

                resultado_df = pd.DataFrame(resultados)

                st.success("Combinaciones generadas.")

                st.dataframe(
                    resultado_df,
                    use_container_width=True,
                    hide_index=True
                )

                st.download_button(
                    "Descargar combinaciones CSV",
                    resultado_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name="combinaciones.csv",
                    mime="text/csv"
                )

                st.warning(
                    "Las frecuencias históricas no predicen resultados "
                    "futuros. Los sorteos independientes conservan sus "
                    "probabilidades originales."
                )

        # ==================================
        # TOP 5 COMBINACIONES ESTADÍSTICAS
        # ==================================

        elif seccion == "TOP 5 Combinaciones Estadísticas":

            st.header("🏆 TOP 5 Combinaciones Estadísticas")
            st.caption("Análisis basado en datos históricos reales — No garantiza resultados futuros")

            if len(df) < 10:
                st.warning(
                    "Se necesitan al menos 10 sorteos válidos para generar el análisis estadístico. "
                    f"Actualmente hay {len(df)} sorteos. Importa más archivos en la sección 'Importar archivos'."
                )
            else:
                with st.spinner("Calculando análisis estadístico avanzado..."):
                    analisis = analisis_completo(df)

                if "error" in analisis:
                    st.error(analisis["error"])
                else:
                    # Métricas generales
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Total sorteos analizados", analisis["total_sorteos"])
                    c2.metric("Rango de fechas", f"{analisis['fecha_primero']} → {analisis['fecha_ultimo']}")
                    c3.metric("Número más frecuente", max(analisis["frecuencias"], key=analisis["frecuencias"].get))
                    c4.metric("Parejas únicas detectadas", len(analisis["top_parejas"]))

                    st.divider()

                    # Top 5 Combinaciones
                    st.subheader("🥇 Las 5 mejores combinaciones estadísticas")

                    for i, comb in enumerate(analisis["top_5_combinaciones"]):
                        with st.container():
                            col_num, col_score, col_detalle = st.columns([2, 1, 3])

                            with col_num:
                                st.markdown(f"### **#{i+1}**")
                                nums_str = " - ".join(f"`{n:02d}`" for n in comb["numeros"])
                                st.markdown(f"**{nums_str}**")
                                st.caption(f"Puntuación total: **{comb['puntuacion']:.1f}**")

                            with col_score:
                                # Gráfico de barras de puntuaciones
                                detalle_df = pd.DataFrame(
                                    list(comb["detalle_puntuaciones"].items()),
                                    columns=["Criterio", "Puntuación"]
                                )
                                st.bar_chart(detalle_df.set_index("Criterio"))

                            with col_detalle:
                                st.markdown("**📊 Análisis de la combinación**")
                                st.write(comb["explicacion"])

                                with st.expander("Ver detalle de puntuaciones"):
                                    for criterio, valor in comb["detalle_puntuaciones"].items():
                                        st.write(f"• {criterio}: {valor:.1f}")

                                if comb["parejas"]:
                                    st.write("**🔗 Parejas frecuentes en esta combinación:**")
                                    for p in comb["parejas"][:3]:
                                        st.write(f"• {p['pareja']}: {p['veces']} veces")

                                if comb["trios"]:
                                    st.write("**🔺 Tríos frecuentes en esta combinación:**")
                                    for t in comb["trios"][:2]:
                                        st.write(f"• {t['trio']}: {t['veces']} veces")

                            st.divider()

                    # Secciones de análisis detallado
                    with st.expander("📈 Frecuencias globales (1-49)", expanded=False):
                        freq_df = pd.DataFrame({
                            "Número": list(analisis["frecuencias"].keys()),
                            "Apariciones": list(analisis["frecuencias"].values())
                        }).sort_values("Apariciones", ascending=False)
                        st.bar_chart(freq_df.set_index("Número"))
                        st.dataframe(freq_df, use_container_width=True, hide_index=True)

                    with st.expander("📅 Frecuencias recientes (últimos 20 sorteos)", expanded=False):
                        freq_rec = pd.DataFrame({
                            "Número": list(analisis["frecuencias_recientes"].keys()),
                            "Apariciones": list(analisis["frecuencias_recientes"].values())
                        }).sort_values("Apariciones", ascending=False)
                        st.bar_chart(freq_rec.set_index("Número"))
                        st.dataframe(freq_rec, use_container_width=True, hide_index=True)

                    with st.expander("🔗 Top 20 Parejas más frecuentes", expanded=False):
                        if analisis["top_parejas"]:
                            pares_df = pd.DataFrame(analisis["top_parejas"])
                            st.dataframe(pares_df, use_container_width=True, hide_index=True)

                    with st.expander("🔺 Top 20 Tríos más frecuentes", expanded=False):
                        if analisis["top_trios"]:
                            trios_df = pd.DataFrame(analisis["top_trios"])
                            st.dataframe(trios_df, use_container_width=True, hide_index=True)

                    with st.expander("📆 Números en días consecutivos", expanded=False):
                        if analisis["consecutivos_dias"]:
                            consec_df = pd.DataFrame({
                                "Número": list(analisis["consecutivos_dias"].keys()),
                                "Máx. días consecutivos": list(analisis["consecutivos_dias"].values())
                            }).sort_values("Máx. días consecutivos", ascending=False)
                            st.dataframe(consec_df, use_container_width=True, hide_index=True)

                    with st.expander("🔄 Parejas en días consecutivos", expanded=False):
                        if analisis["pares_consecutivos"]:
                            pares_consec_df = pd.DataFrame({
                                "Pareja": list(analisis["pares_consecutivos"].keys()),
                                "Máx. días consecutivos": list(analisis["pares_consecutivos"].values())
                            }).sort_values("Máx. días consecutivos", ascending=False)
                            st.dataframe(pares_consec_df, use_container_width=True, hide_index=True)

                    with st.expander("📊 Frecuencias por día de la semana", expanded=False):
                        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                        for dia in range(7):
                            freq = analisis["frecuencias_por_dia"].get(str(dia), analisis["frecuencias_por_dia"].get(dia, {}))
                            if freq and any(freq.values()):
                                st.write(f"**{dias_semana[dia]}**")
                                dia_df = pd.DataFrame({
                                    "Número": list(freq.keys()),
                                    "Apariciones": list(freq.values())
                                }).sort_values("Apariciones", ascending=False)
                                st.bar_chart(dia_df.set_index("Número"))

                    # Botón para descargar reporte
                    st.divider()
                    reporte_df = pd.DataFrame([{
                        "Ranking": i+1,
                        "Números": " - ".join(map(str, c["numeros"])),
                        "Puntuación": c["puntuacion"],
                        "Explicación": c["explicacion"]
                    } for i, c in enumerate(analisis["top_5_combinaciones"])])

                    st.download_button(
                        "📥 Descargar reporte TOP 5 (CSV)",
                        reporte_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"top5_combinaciones_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )

                    st.info(
                        "⚠️ **Aviso legal**: Este análisis estudia patrones históricos. "
                        "Los sorteos de lotería son eventos independientes y aleatorios. "
                        "Las frecuencias pasadas no predicen resultados futuros. "
                        "Juega con responsabilidad."
                    )

        # ==================================
        # COMPROBAR RESULTADO
        # ==================================

        elif seccion == "Comprobar resultado":

            st.header("✅ Comprobar un nuevo resultado")

            st.write(
                "Introduce los cinco números principales y el complementario."
            )

            entrada = []

            columnas = st.columns(5)

            for i, columna in enumerate(columnas):
                entrada.append(
                    columna.number_input(
                        f"Número {i + 1}",
                        min_value=1,
                        max_value=49,
                        value=i + 1,
                        key=f"principal_{i}"
                    )
                )

            complementario_nuevo = st.number_input(
                "Número complementario",
                min_value=1,
                max_value=49,
                value=6,
                key="nuevo_complementario"
            )

            if st.button("Comprobar resultado"):

                if len(set(entrada)) != 5:
                    st.error("Los cinco números deben ser diferentes.")

                elif complementario_nuevo in entrada:
                    st.error(
                        "El complementario no puede coincidir "
                        "con los cinco números principales."
                    )

                else:
                    st.subheader("Frecuencias históricas de tu resultado")

                    for numero in sorted(entrada):
                        st.write(
                            f"Número {numero}: "
                            f"{int(frecuencias[numero])} apariciones"
                        )

                    st.write(
                        "Complementario: "
                        f"{int(frecuencia_complementario[complementario_nuevo])} "
                        "apariciones históricas."
                    )

                    st.info(
                        "Esta consulta estudia frecuencias. "
                        "La comparación con combinaciones generadas "
                        "se incorporará en la siguiente fase."
                    )

        # ==================================
        # HISTORIAL
        # ==================================

        elif seccion == "Historial":

            st.header("📚 Historial de sorteos")

            st.write(f"Total de resultados: {len(df)}")

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "Descargar historial CSV",
                df.to_csv(index=False).encode("utf-8-sig"),
                file_name="historial_sorteos.csv",
                mime="text/csv"
            )

            st.caption(
                "El archivo original permanece guardado en la carpeta datos."
            )

st.sidebar.divider()
st.sidebar.caption("ANALIZADOR INTELIGENTE 1-49")
st.sidebar.caption("Versión 0.3")
st.sidebar.caption("Importación multi-formato + análisis estadístico completo")
