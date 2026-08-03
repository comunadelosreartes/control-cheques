import streamlit as st
import io
from streamlit_gsheets import GSheetsConnection
from datetime import date
import pandas as pd
import calendar
import streamlit as st

# --- CONTROL DE ACCESO SIMPLE ---
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
        if st.session_state["password"] == "comuna2026":  # <-- Cambia esta clave por la que prefieras
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Contraseña de acceso:", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Contraseña de acceso:", type="password", on_change=password_entered, key="password")
        st.error("😕 Contraseña incorrecta")
        return False
    else:
        return True

if not check_password():
    st.stop()  # Detiene la ejecución si no se autenticó
# --------------------------------
# Configuración de la página
st.set_page_config(page_title="Gestión de Cheques", page_icon="💳", layout="wide")

# Inicializar conexión con Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Menú lateral para navegar entre secciones
st.sidebar.title("📌 Menú Principal")
opcion = st.sidebar.radio(
    "Seleccione una opción:",
    [
        "✍️ Ingresar Cheque", 
        "🔍 Gestionar / Marcar Cobrados", 
        "📅 Calendario / Flujo de Pagos",
        "📊 Informes / Descargar Excel",
        "🧮 Ensayo y Carga Masiva"
    ]
)

# =============================================================================
# OPCIÓN 1: INGRESAR NUEVO CHEQUE
# =============================================================================
if opcion == "✍️ Ingresar Cheque":
    st.title("💳 Ingreso de Nuevos Cheques")
    st.subheader("Complete los datos del cheque:")

    # Formulario de ingreso
    with st.form("form_cheque", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha_emision = st.date_input("Fecha de Emisión", value=date.today())
            tipo_cheque = st.selectbox("Tipo de Cheque", ["Cheque físico", "echeq"])
            cobrado = st.selectbox("¿Cobrado?", ["NO", "SI"])
            
        with col2:
            fecha_acreditacion = st.date_input("Fecha de Acreditación", value=date.today())
            nro_cheque = st.text_input("N° de Cheque", placeholder="Ej: 00012345")
            monto = st.number_input("Monto ($)", min_value=0.0, step=100.0, format="%.2f")
        
        beneficiario = st.text_input("Beneficiario")
        submit = st.form_submit_button("Guardar Cheque")

# Procesar el envío del formulario
    if submit:
        if not nro_cheque.strip():
            st.error("Por favor, ingrese el número de cheque.")
        elif not beneficiario.strip():
            st.error("Por favor, ingrese el nombre del beneficiario.")
        elif monto <= 0:
            st.error("El monto debe ser mayor a cero.")
        else:
            try:
                # 1. Leer los datos existentes de la planilla
                data_existente = conn.read(ttl=0)

                # ⚠️ VALIDACIÓN DE DUPLICADOS ⚠️
                if not data_existente.empty and "Nro Cheque" in data_existente.columns:
                    # Convertimos a texto para comparar exactamente igual
                    cheques_existentes = (
                        data_existente["Nro Cheque"].astype(str).str.strip().tolist()
                    )

                    if nro_cheque.strip() in cheques_existentes:
                        st.warning(
                            f"⚠️ **¡Alerta!** El cheque N° **{nro_cheque.strip()}** ya existe en el sistema. Por favor, verifique el número."
                        )
                        st.stop()  # Detiene el guardado para evitar duplicar datos

                # 2. Crear el nuevo registro
                nuevo_cheque = pd.DataFrame(
                    [
                        {
                            "Fecha Emision": fecha_emision.strftime("%Y-%m-%d"),
                            "Fecha Acreditacion": fecha_acreditacion.strftime(
                                "%Y-%m-%d"
                            ),
                            "Nro Cheque": nro_cheque.strip(),
                            "Beneficiario": beneficiario.strip(),
                            "Tipo": tipo_cheque,
                            "Monto": monto,
                            "Cobrado": cobrado,
                        }
                    ]
                )

                # 3. Concatenar el nuevo registro
                df_actualizado = pd.concat(
                    [data_existente, nuevo_cheque], ignore_index=True
                )

                # 4. Enviar a Google Sheets
                conn.update(data=df_actualizado)

                st.success(
                    f"¡Cheque N° **{nro_cheque}** guardado con éxito para **{beneficiario}**!"
                )
            except Exception as e:
                st.error(f"Error al guardar en Google Sheets: {e}")

    # Tabla de registros cargados
    st.divider()
    st.subheader("📋 Historial Completo de Cheques")
    try:
        datos_actuales = conn.read(ttl=0)
        st.dataframe(datos_actuales, use_container_width=True)
    except Exception:
        st.info("Aún no se han podido cargar los datos de la planilla.")

# =============================================================================
# OPCIÓN 2: GESTIONAR / MARCAR COBRADOS
# =============================================================================
elif opcion == "🔍 Gestionar / Marcar Cobrados":
    st.title("🔍 Buscador y Gestión de Cobros")
    st.caption("Filtre cheques por número o beneficiario y actualice su estado a 'SI' o 'NO'.")
    
    try:
        df = conn.read(ttl=0)
        
        col_busqueda, col_filtro = st.columns([3, 1])
        with col_busqueda:
            busqueda = st.text_input("🔎 Buscar por N° de Cheque o Beneficiario:", placeholder="Escriba el número o nombre...")
        with col_filtro:
            estado_filtro = st.selectbox("Filtrar Estado:", ["Pendientes (NO)", "Todos", "Cobrados (SI)"])

        df_filtrado = df.copy()
        
        # Filtro de estado
        if estado_filtro == "Pendientes (NO)":
            df_filtrado = df_filtrado[df_filtrado["Cobrado"].astype(str).str.upper().isin(["NO", "NAN", "NONE", ""])]
        elif estado_filtro == "Cobrados (SI)":
            df_filtrado = df_filtrado[df_filtrado["Cobrado"].astype(str).str.upper() == "SI"]

        # Filtro por texto
        if busqueda.strip():
            mask_num = df_filtrado["Nro Cheque"].astype(str).str.contains(busqueda, case=False, na=False)
            mask_ben = df_filtrado["Beneficiario"].astype(str).str.contains(busqueda, case=False, na=False)
            df_filtrado = df_filtrado[mask_num | mask_ben]

        st.subheader(f"Resultados ({len(df_filtrado)} cheques encontrados)")

        if df_filtrado.empty:
            st.info("No se encontraron cheques con el criterio de búsqueda ingresado.")
        else:
            # Editor interactivo de datos
            df_editable = st.data_editor(
                df_filtrado,
                column_config={
                    "Cobrado": st.column_config.SelectboxColumn(
                        "¿Cobrado?",
                        options=["NO", "SI"],
                        required=True,
                    )
                },
                disabled=["Fecha Emision", "Fecha Acreditacion", "Nro Cheque", "Beneficiario", "Tipo", "Monto"],
                hide_index=True,
                use_container_width=True
            )

            # Botón para persistir los cambios en Google Sheets
            if st.button("💾 Guardar Cambios en Google Sheets", type="primary"):
                df.update(df_editable)
                conn.update(data=df)
                st.success("¡Estados de cobro actualizados correctamente!")
                st.rerun()

    except Exception as e:
        st.error(f"Error al procesar la solicitud: {e}")

# =============================================================================
# OPCIÓN 3: CALENDARIO Y FLUJO DE PAGOS
# =============================================================================
elif opcion == "📅 Calendario / Flujo de Pagos":
    st.title("📅 Calendario de Vencimientos y Flujo de Pagos")
    st.caption("Analice la carga diaria de cheques tanto en vista de almanaque mensual como en gráficos de tendencia.")

    try:
        df = conn.read(ttl=0)
        
        # Filtrar cheques no cobrados / pendientes
        df_pendientes = df[df["Cobrado"].astype(str).str.upper().isin(["NO", "NAN", "NONE", ""])].copy()
        
        if df_pendientes.empty:
            st.success("🎉 ¡No hay cheques pendientes de cobro registrados!")
        else:
            df_pendientes["Fecha Acreditacion"] = pd.to_datetime(df_pendientes["Fecha Acreditacion"])
            df_pendientes["Monto"] = pd.to_numeric(df_pendientes["Monto"], errors="coerce").fillna(0)

            # Modos de visualización
            modo_vista = st.radio(
                "Seleccione el modo de visualización:",
                ["🗓️ Almanaque Mensual", "📊 Gráficos y Listado Diario"],
                horizontal=True
            )

            st.divider()

            # -----------------------------------------------------------------
            # VISTA 1: ALMANAQUE MENSUAL
            # -----------------------------------------------------------------
            if modo_vista == "🗓️ Almanaque Mensual":
                col_m, col_a, _ = st.columns([2, 2, 4])
                with col_m:
                    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    mes_sel_nombre = st.selectbox("Mes", meses_nombres, index=date.today().month - 1)
                    mes_sel = meses_nombres.index(mes_sel_nombre) + 1
                with col_a:
                    anio_sel = st.number_input("Año", min_value=2024, max_value=2035, value=date.today().year)

                df_mes = df_pendientes[
                    (df_pendientes["Fecha Acreditacion"].dt.month == mes_sel) & 
                    (df_pendientes["Fecha Acreditacion"].dt.year == anio_sel)
                ]

                total_mes = df_mes["Monto"].sum() if not df_mes.empty else 0
                cant_mes = len(df_mes) if not df_mes.empty else 0
                
                m_col1, m_col2 = st.columns(2)
                m_col1.metric(f"Monto Total en {mes_sel_nombre}", f"${total_mes:,.2f}")
                m_col2.metric(f"Cheques Pendientes en {mes_sel_nombre}", f"{cant_mes} cheques")
                
                st.markdown("""
                <style>
                    .cal-header { background-color: #1a237e; color: white; text-align: center; font-weight: bold; padding: 6px; border: 1px solid #0d47a1; font-size: 14px; }
                    .cal-day-box { border: 1px solid #bbb; min-height: 110px; background-color: #ffffff; padding: 4px; position: relative; font-size: 12px; }
                    .cal-day-empty { border: 1px solid #e0e0e0; min-height: 110px; background-color: #f5f5f5; }
                    .cal-day-number { font-weight: bold; font-size: 15px; color: #1a237e; }
                    .cal-day-busy { background-color: #fffde7 !important; border: 2px solid #fbc02d !important; }
                    .cal-item { font-size: 10px; color: #333; background: #e8eaf6; border-radius: 3px; padding: 2px 4px; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
                    .cal-saldo { position: absolute; bottom: 3px; right: 5px; font-weight: bold; font-size: 11px; color: #b71c1c; }
                </style>
                """, unsafe_allow_html=True)

                cal = calendar.Calendar(firstweekday=6)
                mes_dias = cal.monthdayscalendar(anio_sel, mes_sel)
                dias_semana = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
                
                cols = st.columns(7)
                for i, idx_col in enumerate(cols):
                    idx_col.markdown(f'<div class="cal-header">{dias_semana[i]}</div>', unsafe_allow_html=True)

                for semana in mes_dias:
                    cols_sem = st.columns(7)
                    for i, dia in enumerate(semana):
                        with cols_sem[i]:
                            if dia == 0:
                                st.markdown('<div class="cal-day-empty"></div>', unsafe_allow_html=True)
                            else:
                                fecha_str = f"{anio_sel}-{mes_sel:02d}-{dia:02d}"
                                cheques_dia = df_mes[df_mes["Fecha Acreditacion"].dt.strftime("%Y-%m-%d") == fecha_str] if not df_mes.empty else pd.DataFrame()
                                monto_dia = cheques_dia["Monto"].sum() if not cheques_dia.empty else 0
                                clase_busy = " cal-day-busy" if monto_dia > 0 else ""

                                html_contenido = f'<div class="cal-day-box{clase_busy}">'
                                html_contenido += f'<div class="cal-day-number">{dia}</div>'

                                if not cheques_dia.empty:
                                    for _, chk in cheques_dia.head(2).iterrows():
                                        nro_txt = f"N°{chk.get('Nro Cheque', '')}" if pd.notna(chk.get('Nro Cheque')) else ""
                                        html_contenido += f'<div class="cal-item">{nro_txt} | {str(chk["Beneficiario"])[:10]}</div>'
                                    if len(cheques_dia) > 2:
                                        html_contenido += f'<div class="cal-item">+ {len(cheques_dia)-2} más...</div>'

                                saldo_text = f"${monto_dia:,.2f}" if monto_dia > 0 else "0.00"
                                html_contenido += f'<div class="cal-saldo">{saldo_text}</div>'
                                html_contenido += '</div>'

                                st.markdown(html_contenido, unsafe_allow_html=True)

            # -----------------------------------------------------------------
            # VISTA 2: GRÁFICOS Y DETALLE DIARIO
            # -----------------------------------------------------------------
            elif modo_vista == "📊 Gráficos y Listado Diario":
                monto_total_pendiente = df_pendientes["Monto"].sum()
                cant_cheques_pendientes = len(df_pendientes)

                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Total General Pendiente", f"${monto_total_pendiente:,.2f}")
                col_m2.metric("Cantidad Total de Cheques", f"{cant_cheques_pendientes} cheques")

                st.subheader("📊 Carga Diaria de Acreditaciones ($)")

                flujo_diario = df_pendientes.groupby(
                    df_pendientes["Fecha Acreditacion"].dt.strftime("%Y-%m-%d")
                )["Monto"].sum().reset_index()
                flujo_diario.columns = ["Fecha Acreditación", "Monto Total ($)"]

                st.bar_chart(
                    flujo_diario,
                    x="Fecha Acreditación",
                    y="Monto Total ($)",
                    use_container_width=True
                )

                st.divider()
                st.subheader("📋 Detalle de Cheques por Día")
                
                fechas_disponibles = flujo_diario["Fecha Acreditación"].tolist()
                fecha_seleccionada = st.selectbox("Seleccione una fecha para ver el detalle:", options=fechas_disponibles)

                if fecha_seleccionada:
                    detalle_dia = df_pendientes[df_pendientes["Fecha Acreditacion"].dt.strftime("%Y-%m-%d") == fecha_seleccionada]
                    st.write(f"Cheques a acreditar el día **{fecha_seleccionada}**:")
                    
                    cols_mostrar = [c for c in ["Nro Cheque", "Beneficiario", "Tipo", "Monto", "Fecha Emision"] if c in detalle_dia.columns]
                    st.dataframe(
                        detalle_dia[cols_mostrar],
                        use_container_width=True,
                        hide_index=True
                    )

    except Exception as e:
        st.error(f"Error al generar la sección de calendario: {e}")

# =============================================================================
# OPCIÓN 4: INFORMES Y DESCARGA EN EXCEL
# =============================================================================
elif opcion == "📊 Informes / Descargar Excel":
    st.title("📊 Generador de Informes y Control de Deuda")
    st.caption("Filtre por rango de fechas y estado de cobro para consultar la deuda pendiente y exportar a Excel.")

    try:
        df = conn.read(ttl=0)

        if not df.empty:
            # 1. Convertir la fecha de acreditación a formato Datetime para operar
            df["Fecha_DT"] = pd.to_datetime(df["Fecha Acreditacion"], errors="coerce")

            # 2. Calcular fecha "Desde" por defecto: primer cheque pendiente (Cobrado != SI)
            df_pendientes = df[~df["Cobrado"].astype(str).str.upper().isin(["SI"])]

            if not df_pendientes.empty and df_pendientes["Fecha_DT"].notna().any():
                fecha_desde_defecto = df_pendientes["Fecha_DT"].min().date()
            else:
                fecha_desde_defecto = date.today()

            fecha_hasta_defecto = date.today()

            # 3. Filtros en Pantalla (Fechas y Estado)
            col1, col2, col3 = st.columns([2, 2, 3])
            with col1:
                fecha_desde = st.date_input("Fecha Desde:", value=fecha_desde_defecto, format="DD/MM/YYYY")
            with col2:
                fecha_hasta = st.date_input("Fecha Hasta:", value=fecha_hasta_defecto, format="DD/MM/YYYY")
            with col3:
                filtro_estado = st.selectbox(
                    "Estado a Consultar:",
                    ["🔴 Pendientes / Deuda (NO)", "📋 Todos los Cheques", "🟢 Cobrados (SI)"],
                    index=0  # Por defecto selecciona Pendientes
                )

            # 4. Aplicar Filtro de Fechas
            mask_fechas = (df["Fecha_DT"].dt.date >= fecha_desde) & (df["Fecha_DT"].dt.date <= fecha_hasta)
            df_informe = df[mask_fechas].copy()

            # 5. Aplicar Filtro de Estado
            if filtro_estado == "🔴 Pendientes / Deuda (NO)":
                df_informe = df_informe[~df_informe["Cobrado"].astype(str).str.upper().isin(["SI"])]
            elif filtro_estado == "🟢 Cobrados (SI)":
                df_informe = df_informe[df_informe["Cobrado"].astype(str).str.upper().isin(["SI"])]

            # Quitar la columna auxiliar de fecha
            df_informe = df_informe.drop(columns=["Fecha_DT"])

            # 6. Cálculo de Totales y Métricas Visuales
            st.divider()
            
            # Asegurar que Monto sea numérico para sumar
            df_informe["Monto_Num"] = pd.to_numeric(df_informe["Monto"], errors="coerce").fillna(0)
            monto_total_informe = df_informe["Monto_Num"].sum()

            m1, m2 = st.columns(2)
            m1.metric("Cantidad de Cheques", f"{len(df_informe)} registros")
            
            # Mostrar etiqueta personalizada según el filtro elegido
            if filtro_estado == "🔴 Pendientes / Deuda (NO)":
                m2.metric("💸 Total Deuda Pendiente", f"${monto_total_informe:,.2f}")
            elif filtro_estado == "🟢 Cobrados (SI)":
                m2.metric("✅ Total Cobrado", f"${monto_total_informe:,.2f}")
            else:
                m2.metric("Monto Total en Rango", f"${monto_total_informe:,.2f}")

            # Eliminar la columna temporal de monto numérico para la tabla
            df_informe_vista = df_informe.drop(columns=["Monto_Num"])

            # 7. Vista previa en pantalla
            st.subheader(f"📋 Vista Previa ({len(df_informe)} cheques)")
            st.dataframe(df_informe_vista, use_container_width=True, hide_index=True)

            # 8. Preparación y Botón de Descargar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_informe_vista.to_excel(writer, index=False, sheet_name="Informe_Cheques")
            data_excel = output.getvalue()

            # Nombre de archivo dinámico según filtro
            tag_estado = "deuda_pendiente" if "Pendientes" in filtro_estado else ("cobrados" if "Cobrados" in filtro_estado else "todos")
            
            st.download_button(
                label="📥 Descargar Informe en Excel (.xlsx)",
                data=data_excel,
                file_name=f"informe_{tag_estado}_{fecha_desde}_al_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("Aún no hay cheques registrados en la planilla.")

    except Exception as e:
        st.error(f"Error al generar el informe: {e}")
# =============================================================================
# OPCIÓN 5: ENSAYO Y CARGA MASIVA DE CHEQUES
# =============================================================================
elif opcion == "🧮 Ensayo y Carga Masiva":
    st.title("🧮 Ensayo y Planificación de Carga de Cheques")
    st.caption(
        "Simule la distribución de un pago en varios cheques, verifique la carga diaria en el calendario y confirme la carga masiva a Google Sheets."
    )

    try:
        df_existente = conn.read(ttl=0)
    except Exception as e:
        df_existente = pd.DataFrame()
        st.warning(
            "No se pudieron cargar los cheques existentes para verificar carga diaria."
        )

    # -------------------------------------------------------------------------
    # PASO 1: PARÁMETROS DEL PAGO Y CÁLCULO DE MONTOS
    # -------------------------------------------------------------------------
    st.subheader("1️⃣ Parámetros del Pago")

    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        beneficiario_sim = st.text_input("Beneficiario / Proveedor:")
    with col2:
        monto_total_sim = st.number_input(
            "Monto Total a Pagar ($):", min_value=0.0, step=1000.0, format="%.2f"
        )
    with col3:
        tipo_cheque_sim = st.selectbox(
            "Tipo de Cheque:", ["Cheque físico", "echeq"]
        )

    col4, col5, col6, col7 = st.columns(4)
    with col4:
        cant_cheques = st.number_input(
            "Cantidad de Cheques:", min_value=1, max_value=20, value=3
        )
    with col5:
        nro_inicial_sim = st.number_input(
            "N° Cheque Inicial:", min_value=1, value=5424
        )
    with col6:
        # Sugerencia de división exacta
        monto_promedio = (
            monto_total_sim / cant_cheques if cant_cheques > 0 else 0.0
        )
        # Redondeo sugerido a miles
        monto_redondo_sugerido = round(monto_promedio, -3)

        monto_propuesto = st.number_input(
            "Monto Redondo Propuesto ($):",
            min_value=0.0,
            value=float(monto_redondo_sugerido),
            step=1000.0,
            format="%.2f",
            help="Monto de anotación sencilla para los primeros cheques.",
        )

    with col7:
        # Cálculo del saldo restante para el último cheque
        if cant_cheques > 1:
            monto_saldo = monto_total_sim - (
                monto_propuesto * (cant_cheques - 1)
            )
        else:
            monto_saldo = monto_total_sim

        st.metric(
            "Monto Último Cheque (Saldo)",
            f"${monto_saldo:,.2f}",
            delta=f"Promedio: ${monto_promedio:,.2f}",
            delta_color="off",
        )

    if monto_saldo < 0:
        st.error(
            "⚠️ El monto propuesto multiplicado por la cantidad de cheques supera el monto total a pagar. Por favor, reduzca el monto propuesto."
        )

    st.divider()

    # -------------------------------------------------------------------------
    # PASO 2: ASIGNACIÓN DE FECHAS Y CONSULTA DE CARGA DIARIA
    # -------------------------------------------------------------------------
    st.subheader("2️⃣ Asignación de Fechas y Verificación de Carga Diaria")
    st.caption(
        "Ajuste las fechas estimadas para cada cheque y consulte la acumulación de compromisos para cada día."
    )

    cheques_generados = []
    hoy = date.today()

    # Prefijo P solo para Cheque Físico
    prefijo = "P" if tipo_cheque_sim == "Cheque físico" else ""

    # Preparar df existente para consulta de acumulado por día
    if not df_existente.empty and "Fecha Acreditacion" in df_existente.columns:
        df_existente["Fecha_DT"] = pd.to_datetime(
            df_existente["Fecha Acreditacion"], errors="coerce"
        ).dt.date
        df_existente["Monto_Num"] = pd.to_numeric(
            df_existente["Monto"], errors="coerce"
        ).fillna(0)
    else:
        df_existente = pd.DataFrame(columns=["Fecha_DT", "Monto_Num"])

    for i in range(cant_cheques):
        col_chq, col_fecha, col_monto, col_info = st.columns([1.5, 2, 2, 3.5])

        # Formatear el número de cheque
        nro_actual = f"{prefijo}{int(nro_inicial_sim) + i}"

        # Asignar monto: los primeros llevan monto_propuesto, el último lleva el saldo
        monto_chq = (
            monto_propuesto if i < cant_cheques - 1 else max(0.0, monto_saldo)
        )

        # Fecha sugerida por defecto (ej: a 30, 45, 60 días...)
        dias_defecto = 30 + (i * 15)
        fecha_sugerida = hoy + timedelta(days=dias_defecto)

        with col_chq:
            st.text_input(
                f"Cheque #{i+1}",
                value=nro_actual,
                disabled=True,
                key=f"nro_{i}",
            )

        with col_fecha:
            fecha_elegi = st.date_input(
                f"Fecha Acreditación #{i+1}:",
                value=fecha_sugerida,
                format="DD/MM/YYYY",
                key=f"fecha_{i}",
            )

        with col_monto:
            st.text_input(
                f"Monto #{i+1}:",
                value=f"${monto_chq:,.2f}",
                disabled=True,
                key=f"monto_{i}",
            )

        # Consultar carga actual en el sistema para la fecha elegida
        monto_cargado_dia = df_existente[
            df_existente["Fecha_DT"] == fecha_elegi
        ]["Monto_Num"].sum()

        with col_info:
            if monto_cargado_dia == 0:
                st.success(f"🟢 **{fecha_elegi.strftime('%d/%m/%Y')}**: Día libre ($0.00 cargados)")
            elif monto_cargado_dia < 2000000:
                st.info(
                    f"🟡 **{fecha_elegi.strftime('%d/%m/%Y')}**: Carga moderada (${monto_cargado_dia:,.2f})"
                )
            else:
                st.warning(
                    f"🔴 **{fecha_elegi.strftime('%d/%m/%Y')}**: Carga alta (${monto_cargado_dia:,.2f})"
                )

        cheques_generados.append(
            {
                "Fecha Emision": hoy.strftime("%Y-%m-%d"),
                "Fecha Acreditacion": fecha_elegi.strftime("%Y-%m-%d"),
                "Nro Cheque": nro_actual,
                "Beneficiario": beneficiario_sim.strip(),
                "Tipo": tipo_cheque_sim,
                "Monto": monto_chq,
                "Cobrado": "NO",
            }
        )

    st.divider()

    # -------------------------------------------------------------------------
    # PASO 3: VISTA PREVIA Y CONFIRMACIÓN DE CARGA MASIVA
    # -------------------------------------------------------------------------
    st.subheader("3️⃣ Vista Previa y Carga Masiva")

    df_simulacion = pd.DataFrame(cheques_generados)

    # Formatear la vista previa para mejor lectura
    df_simulacion_vista = df_simulacion.copy()
    df_simulacion_vista["Monto"] = df_simulacion_vista["Monto"].apply(
        lambda x: f"${x:,.2f}"
    )

    st.dataframe(df_simulacion_vista, use_container_width=True, hide_index=True)

    col_btn, _ = st.columns([2, 2])
    with col_btn:
        btn_confirmar = st.button(
            "🚀 Confirmar y Cargar Lote a Google Sheets",
            type="primary",
            use_container_width=True,
        )

    if btn_confirmar:
        if not beneficiario_sim.strip():
            st.error(
                "Por favor, ingrese el nombre del Beneficiario antes de confirmar."
            )
        elif monto_total_sim <= 0:
            st.error(
                "El monto total del pago debe ser mayor a cero para realizar la carga."
            )
        elif monto_saldo < 0:
            st.error("Corrija el monto propuesto antes de confirmar.")
        else:
            try:
                # 1. Leer planilla actual
                data_existente = conn.read(ttl=0)

                # 2. Validar que ninguno de los nuevos cheques exista previamente
                if (
                    not data_existente.empty
                    and "Nro Cheque" in data_existente.columns
                ):
                    cheques_existentes = (
                        data_existente["Nro Cheque"]
                        .astype(str)
                        .str.strip()
                        .tolist()
                    )
                    duplicados = [
                        c["Nro Cheque"]
                        for c in cheques_generados
                        if c["Nro Cheque"] in cheques_existentes
                    ]

                    if duplicados:
                        st.warning(
                            f"⚠️ No se pudo realizar la carga. Los siguientes números de cheque ya existen en el sistema: **{', '.join(duplicados)}**"
                        )
                        st.stop()

                # 3. Concatenar y actualizar Google Sheets
                df_actualizado = pd.concat(
                    [data_existente, df_simulacion], ignore_index=True
                )
                conn.update(data=df_actualizado)

                st.balloons()
                st.success(
                    f"🎉 ¡Lote de **{cant_cheques} cheques** cargado con éxito para **{beneficiario_sim}**!"
                )

            except Exception as e:
                st.error(f"Error al guardar el lote en Google Sheets: {e}")
                
