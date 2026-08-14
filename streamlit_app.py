# streamlit_app.py - Web UI (optional)
import streamlit as st
import tempfile
import zipfile
from pathlib import Path
import pandas as pd
import io
from processor import process_batch_files, parse_cp_file

st.set_page_config(layout="wide", page_title="Thermo Data Analysis")

st.title("热电材料数据分析系统（Web 原型）")
st.markdown("上传 ZEM-3 / LFA 测试文件（多文件），输入 Cp 或上传 Cp_vs_T 表，批量处理并查看/下载结果。")

with st.sidebar:
    st.header("参数")
    cp_mode = st.radio("Cp 输入方式", ("常数 Cp (J/kgK)", "上传 Cp_vs_T CSV"))
    cp_value = None
    cp_file = None
    if cp_mode.startswith("常数"):
        cp_value = st.number_input("Cp 常数 (J/kgK)", value=200.0, format="%.3f")
    else:
        cp_file = st.file_uploader("上传 Cp_vs_T CSV (列: T, Cp)", type=["csv"])
    density_override = st.number_input("密度覆盖 (kg/m3) - 可选，留空使用 LFA header", value=0.0, format="%.2f")
    if density_override <= 0:
        density_override = None
    st.markdown("---")
    st.markdown("输出选项")
    include_html = st.checkbox("生成交互式 HTML 图 (plotly)", value=True)
    zip_name = st.text_input("打包下载文件名", value="thermo_results.zip")

st.header("1) 上传文件（可多选）")
uploaded = st.file_uploader("拖拽或选择 ZEM / LFA 文件", accept_multiple_files=True, type=None)
if uploaded:
    st.write(f"已选择 {len(uploaded)} 个文件")
    for f in uploaded:
        st.write(f"- {f.name} ({f.type or 'unknown'})")

process_button = st.button("开始批处理")

if process_button:
    if not uploaded:
        st.warning("请先上传文件")
    else:
        tmpdir = Path(tempfile.mkdtemp(prefix="thermo_"))
        for f in uploaded:
            p = tmpdir / f.name
            p.write_bytes(f.read())
        st.info(f"已上传并保存到临时目录：{tmpdir}")

        cp_path = None
        cp_val = None
        if cp_mode.startswith("常数"):
            cp_val = float(cp_value)
        else:
            if not cp_file:
                st.warning("请选择或上传 Cp_vs_T CSV")
                st.stop()
            cp_bytes = cp_file.read()
            cp_path = tmpdir / "cp_table.csv"
            cp_path.write_bytes(cp_bytes)

        st.info("开始解析与计算（可能需要几秒钟）...")
        results_dir, summary_df = process_batch_files(
            input_dir=str(tmpdir),
            output_dir=str(tmpdir / "out"),
            cp_value=cp_val,
            cp_file=str(cp_path) if cp_path else None,
            force_density=density_override,
            generate_html=include_html
        )

        st.success("处理完成")
        st.write("汇总：")
        st.dataframe(summary_df.fillna(""))

        out_path = Path(results_dir)
        files = list(out_path.glob("*"))
        st.write(f"生成文件 {len(files)} 个")
        for f in files:
            st.write(f"- {f.name}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(f, arcname=f.name)
        zip_buf.seek(0)
        st.download_button(label="下载所有结果 (ZIP)", data=zip_buf, file_name=zip_name, mime="application/zip")

        processed_files = sorted(out_path.glob("*_processed.csv"))
        if processed_files:
            st.header("示例图（来自第一个 processed 文件）")
            df0 = pd.read_csv(processed_files[0])
            if 'T_K' in df0.columns and 'ZT_calc' in df0.columns:
                st.line_chart(df0.set_index('T_K')['ZT_calc'])
            if include_html:
                html_files = list(out_path.glob("*_metrics.html"))
                if html_files:
                    st.markdown("交互式 HTML 已打包在 ZIP 中；也可单独打开。")
