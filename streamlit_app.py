# streamlit_app.py
# Streamlit UI to upload ZEM and LFA files, set units/parameters, compute ZT and download Origin-ready CSV.

import streamlit as st
from pathlib import Path
import pandas as pd
import io
import zipfile
import plotly.express as px
import plotly.graph_objects as go
from processor import parse_zem, parse_lfa, compute_thermo, export_origin_csv

st.set_page_config(page_title="Thermo ZT Calculator", layout="wide")
st.title("Thermo ZT Calculator — Upload ZEM & LFA, compute ZT")

st.sidebar.header("Upload")
zem_file = st.sidebar.file_uploader("ZEM file (CSV/TXT)", type=['csv','txt'], key='zem')
lfa_file = st.sidebar.file_uploader("LFA file (CSV/TXT)", type=['csv','txt'], key='lfa')

st.sidebar.header("Units & parameters")
s_unit = st.sidebar.selectbox("Seebeck unit", ['uV/K','V/K'], index=0)
rho_unit = st.sidebar.selectbox("Resistivity unit", ['mohm_cm','ohm_cm','ohm_m'], index=0,
                                format_func=lambda x: {'mohm_cm':'mΩ·cm','ohm_cm':'Ω·cm','ohm_m':'Ω·m'}[x])
alpha_unit = st.sidebar.selectbox("Thermal diffusivity unit", ['mm2/s','m2/s'], index=0,
                                  format_func=lambda x: {'mm2/s':'mm²/s','m2/s':'m²/s'}[x])
cp = st.sidebar.number_input("Cp (J/kg·K)", value=200.0)
density = st.sidebar.number_input("Density (kg/m³)", value=7000.0)
lorenz = st.sidebar.number_input("Lorenz (W·Ω·K^-2)", value=2.44e-8, format="%.6e")
merge_tol = st.sidebar.number_input("Merge tolerance (K)", value=2.0)

if st.sidebar.button("Compute ZT"):
    if not zem_file:
        st.sidebar.error("Please upload a ZEM file.")
    else:
        with st.spinner("Parsing and computing..."):
            # write temps
            zem_path = Path(".tmp_zem.tmp")
            zem_path.write_bytes(zem_file.getvalue())

            # debug/guard: preview raw file and parsed DataFrame
            raw = zem_path.read_text(errors='ignore')
            st.sidebar.markdown("**ZEM file preview (first 2000 chars)**")
            st.sidebar.code(raw[:2000])

            zem_df = parse_zem(zem_path)
            st.sidebar.markdown("**Parsed ZEM (columns & head)**")
            if zem_df is None or zem_df.empty:
                st.sidebar.write("Parsed ZEM DataFrame is empty — parser 未能识别温度/数值列。")
                st.error("无法解析 ZEM 文件。请确认文件格式，或把文件前 20 行贴到对话中以便进一步调试。")
                st.stop()
            else:
                st.sidebar.write(zem_df.columns.tolist())
                st.sidebar.dataframe(zem_df.head())

            lfa_df = None
            if lfa_file:
                lfa_path = Path(".tmp_lfa.tmp")
                lfa_path.write_bytes(lfa_file.getvalue())
                # show lfa preview
                raw_lfa = lfa_path.read_text(errors='ignore')
                st.sidebar.markdown("**LFA file preview (first 2000 chars)**")
                st.sidebar.code(raw_lfa[:2000])
                lfa_df = parse_lfa(lfa_path)
                st.sidebar.markdown("**Parsed LFA (columns & head)**")
                if lfa_df is None or lfa_df.empty:
                    st.sidebar.write("Parsed LFA DataFrame is empty — parser 未能识别热扩散率/温度列。")
                else:
                    st.sidebar.write(lfa_df.columns.tolist())
                    st.sidebar.dataframe(lfa_df.head())

            try:
                result = compute_thermo(zem_df, lfa_df, cp=cp, density=density,
                                        s_unit=s_unit, rho_unit=rho_unit, alpha_unit=alpha_unit,
                                        lorenz=lorenz, merge_tol_K=merge_tol)
            except Exception as e:
                st.error(f"Computation failed: {e}")
                st.exception(e)
                result = None

        if result is not None and not result.empty:
            st.success("Computation finished")
            # show data table
            st.subheader("Result table (first 100 rows)")
            st.dataframe(result.head(100))

            # interactive plots
            st.subheader("Plots")
            tab1, tab2 = st.tabs(["ZT & PF", "k components & S/rho"])
            with tab1:
                fig1 = px.line(result, x='T', y='ZT', markers=True, title='ZT vs T')
                fig2 = px.line(result, x='T', y='PF_W_per_mK2', markers=True, title='Power Factor (PF) vs T')
                colA, colB = st.columns(2)
                colA.plotly_chart(fig1, use_container_width=True)
                colB.plotly_chart(fig2, use_container_width=True)
            with tab2:
                fig_k = go.Figure()
                if 'k_e_W_per_mK' in result.columns:
                    fig_k.add_trace(go.Line(x=result['T'], y=result['k_e_W_per_mK'], name='k_e'))
                if 'k_l_W_per_mK' in result.columns:
                    fig_k.add_trace(go.Line(x=result['T'], y=result['k_l_W_per_mK'], name='k_l'))
                if 'k_total_W_per_mK' in result.columns:
                    fig_k.add_trace(go.Line(x=result['T'], y=result['k_total_W_per_mK'], name='k_total'))
                fig_k.update_layout(title='Thermal conductivity components vs T', xaxis_title='T (K)', yaxis_title='k (W/mK)')
                fig_s = go.Figure()
                if 'S_uV_per_K' in result.columns or 'S_uV_per_K' not in result.columns and 'S_uV_per_K' in result.columns:
                    # prefer uV column if present
                    if 'S_uV_per_K' in result.columns:
                        fig_s.add_trace(go.Line(x=result['T'], y=result['S_uV_per_K'], name='S (µV/K)'))
                    elif 'S_V_per_K' in result.columns:
                        fig_s.add_trace(go.Line(x=result['T'], y=result['S_V_per_K']*1e6, name='S (µV/K)'))
                if 'rho_ohm_m' in result.columns:
                    fig_s.add_trace(go.Line(x=result['T'], y=result['rho_ohm_m'], name='rho (Ω·m)', yaxis='y2'))
                fig_s.update_layout(title='S and rho vs T', xaxis_title='T (K)',
                                    yaxis=dict(title='S (µV/K)'),
                                    yaxis2=dict(title='rho (Ω·m)', overlaying='y', side='right'))
                st.plotly_chart(fig_k, use_container_width=True)
                st.plotly_chart(fig_s, use_container_width=True)

            # prepare downloads
            csv_buf = io.StringIO()
            result.to_csv(csv_buf, index=False)
            csv_bytes = csv_buf.getvalue().encode('utf-8')
            st.download_button("Download Origin-ready CSV", csv_bytes, file_name="origin_data.csv", mime="text/csv")
            # zip with original files
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr('origin_data.csv', csv_buf.getvalue())
                if zem_file:
                    zf.writestr(f'input/{zem_file.name}', zem_file.getvalue())
                if lfa_file:
                    zf.writestr(f'input/{lfa_file.name}', lfa_file.getvalue())
            zip_buf.seek(0)
            st.download_button("Download results ZIP", zip_buf, file_name="results.zip", mime="application/zip")
        else:
            st.warning("No result produced (check inputs).")

st.markdown("---")
st.info("Notes: choose correct units. Typical defaults: Seebeck µV/K, resistivity mΩ·cm, alpha mm²/s. Cp in J/kgK, density in kg/m³.")
