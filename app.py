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
        "📅 Calendario / Flujo de Pagos"
        "📊 Informes / Descargar Excel"
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
            tipo_cheque = st.selectbox("Tipo de Cheque", ["echeq", "Cheque físico"])
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
                
                # 2. Crear el nuevo registro
                nuevo_cheque = pd.DataFrame([{
                    "Fecha Emision": fecha_emision.strftime("%Y-%m-%d"),
                    "Fecha Acreditacion": fecha_acreditacion.strftime("%Y-%m-%d"),
                    "Nro Cheque": nro_cheque.strip(),
                    "Beneficiario": beneficiario.strip(),
                    "Tipo": tipo_cheque,
                    "Monto": monto,
                    "Cobrado": cobrado
                }])
                
                # 3. Concatenar el nuevo registro
                df_actualizado = pd.concat([data_existente, nuevo_cheque], ignore_index=True)
                
                # 4. Enviar a Google Sheets
                conn.update(data=df_actualizado)
                
                st.success(f"¡Cheque N° **{nro_cheque}** guardado con éxito para **{beneficiario}**!")
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
# =============================================================================
# OPCIÓN 4: INFORMES Y DESCARGA EN EXCEL
# =============================================================================
elif opcion == "📊 Informes / Descargar Excel":
    st.title("📊 Generador de Informes de Cheques")
    st.caption("Seleccione un rango de fechas para previsualizar y exportar a Excel.")

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

            # 3. Filtros de Fecha en pantalla
            col1, col2 = st.columns(2)
            with col1:
                fecha_desde = st.date_input("Fecha Desde:", value=fecha_desde_defecto, format="DD/MM/YYYY")
            with col2:
                fecha_hasta = st.date_input("Fecha Hasta:", value=fecha_hasta_defecto, format="DD/MM/YYYY")

            # 4. Filtrar el DataFrame según el rango
            mask = (df["Fecha_DT"].dt.date >= fecha_desde) & (df["Fecha_DT"].dt.date <= fecha_hasta)
            df_informe = df[mask].copy()

            # Quitar la columna auxiliar
            df_informe = df_informe.drop(columns=["Fecha_DT"])

            # 5. Resumen visual y tabla
            st.divider()
            m1, m2 = st.columns(2)
            
            # Asegurar que Monto sea numérico para sumar
            df_informe["Monto_Num"] = pd.to_numeric(df_informe["Monto"], errors="coerce").fillna(0)
            monto_total_informe = df_informe["Monto_Num"].sum()

            m1.metric("Cantidad de Cheques", f"{len(df_informe)} registros")
            m2.metric("Monto Total en Rango", f"${monto_total_informe:,.2f}")

            # Eliminar la columna temporal de monto numérico para la visualización
            df_informe_vista = df_informe.drop(columns=["Monto_Num"])

            st.subheader(f"📋 Vista Previa ({len(df_informe)} cheques)")
            st.dataframe(df_informe_vista, use_container_width=True, hide_index=True)

            # 6. Preparación y Botón de Descargar Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_informe_vista.to_excel(writer, index=False, sheet_name="Informe_Cheques")
            data_excel = output.getvalue()

            st.download_button(
                label="📥 Descargar Informe en Excel (.xlsx)",
                data=data_excel,
                file_name=f"informe_cheques_{fecha_desde}_al_{fecha_hasta}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.info("Aún no hay cheques registrados en la planilla.")

    except Exception as e:
        st.error(f"Error al generar la sección de calendario: {e}")
