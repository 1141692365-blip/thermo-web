# streamlit_app.py - Web UI (optional)
import streamlit as st
import tempfile
import zipfile
from pathlib import Path
import pandas as pd
import io
import shutil
from processor import process_batch_files, parse_cp_file

st.set_page_config(layout="wide", page_title="Thermo Data Analysis")

st.title("热电材料数据分析系统（Web 原型）")
st.markdown("分别上传 ZEM-3 与 LFA 测试文件，选择/配对后进行 ZT 计算。")

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

st.header("1) 上传文件（分别上传）")
col1, col2 = st.columns(2)
with col1:
    st.subheader("ZEM-3 文件（Seebeck / Resistivity）")
    zem_files = st.file_uploader("上传 ZEM 文件（可多选）", accept_multiple_files=True, type=None, key="zem")
with col2:
    st.subheader("LFA 文件（Thermal diffusivity）")
    lfa_files = st.file_uploader("上传 LFA 文件（可多选）", accept_multiple_files=True, type=None, key="lfa")

# If nothing uploaded yet, show help text
if not zem_files and not lfa_files:
    st.info("请分别上传 ZEM-3 与 LFA 文件，或在侧栏选择 Cp 输入方式。")

# Prepare a temp dir and save uploaded files
if zem_files or lfa_files:
    tmpdir = Path(tempfile.mkdtemp(prefix="thermo_"))
    zem_dir = tmpdir / "zem"
    lfa_dir = tmpdir / "lfa"
    zem_dir.mkdir(parents=True, exist_ok=True)
    lfa_dir.mkdir(parents=True, exist_ok=True)

    for f in zem_files or []:
        (zem_dir / f.name).write_bytes(f.read())
    for f in lfa_files or []:
        (lfa_dir / f.name).write_bytes(f.read())

    st.success(f"已保存上传文件到临时目录：{tmpdir}")

    st.header("2) 选择 / 配对文件")
    # List uploaded files
    zem_list = sorted([p.name for p in zem_dir.iterdir() if p.is_file()])
    lfa_list = sorted([p.name for p in lfa_dir.iterdir() if p.is_file()])

    st.subheader("ZEM 文件（已上传）")
    selected_zem = st.multiselect("选择要处理的 ZEM 文件（多选）", options=zem_list, default=zem_list)

    st.subheader("LFA 文件（已上传）")
    selected_lfa = st.multiselect("选择对应的 LFA 文件（多选）", options=lfa_list, default=lfa_list)

    st.markdown("---")
    st.subheader("自动配对（可选）")
    if st.button("自动按文件名匹配（尝试以 ZEM 名称片段匹配 LFA）"):
        # 简单匹配：寻找 LFA 文件名包含 ZEM 文件 stem 的情形
        auto_pairs = {}
        for z in selected_zem:
            zstem = Path(z).stem
            match = None
            for lf in selected_lfa:
                if zstem in lf or Path(lf).stem in z:
                    match = lf
                    break
            auto_pairs[z] = match
        st.write("��动匹配结果（若未匹配请手动选择）")
        for z, m in auto_pairs.items():
            st.write(f"- {z}  →  {m or '未匹配'}")

    st.markdown("或者手动为每个 ZEM 选择一个 LFA（下方选择会复制到处理目录）")
    manual_map = {}
    if selected_zem:
        for z in selected_zem:
            choice = st.selectbox(f"为 ZEM `{z}` 选择对应的 LFA (或空表示不强配)", options=["(不强配)"] + selected_lfa, key=f"map_{z}")
            if choice != "(不强配)":
                manual_map[z] = choice

    st.markdown("---")
    st.header("3) 开始批处理")
    process_button = st.button("开始批处理（仅处理上面选择的文件）")

    if process_button:
        # create an input_selected dir that contains only the chosen files (ZEM + selected LFA)
        sel_dir = tmpdir / "input_selected"
        sel_dir.mkdir(parents=True, exist_ok=True)

        # copy selected ZEMs
        for z in selected_zem:
            shutil.copy(zem_dir / z, sel_dir / z)
        # copy selected LFAs
        # include both manual-mapped LFAs and the global selected_lfa set (avoid duplicates)
        mapped_lfas = set(manual_map.values())
        for lf in selected_lfa:
            shutil.copy(lfa_dir / lf, sel_dir / lf)
        # ensure manual-mapped ones are present (they are included above)
        st.info(f"将 {len(selected_zem)} 个 ZEM 文件和 {len(selected_lfa)} 个 LFA 文件复制到临时处理目录。")
        # prepare cp function or cp file
        cp_path = None
        cp_val = None
        if cp_mode.startswith("常数"):
            cp_val = float(cp_value)
        else:
            if not cp_file:
                st.warning("请选择或上传 Cp_vs_T CSV")
                st.stop()
            cp_bytes = cp_file.read()
            cp_path = sel_dir / "cp_table.csv"
            cp_path.write_bytes(cp_bytes)

        st.info("开始解析与计算（可能需要几秒钟）...")
        try:
            results_dir, summary_df = process_batch_files(
                input_dir=str(sel_dir),
                output_dir=str(sel_dir / "out"),
                cp_value=cp_val,
                cp_file=str(cp_path) if cp_path else None,
                force_density=density_override,
                generate_html=include_html
            )
        except Exception as e:
            st.error(f"处理时发生错误：{e}")
        else:
            st.success("处理完成")
            st.write("汇总：")
            st.dataframe(summary_df.fillna(""))
            out_path = Path(results_dir)
            files = list(out_path.glob("*"))
            st.write(f"生成文件 {len(files)} 个")
            for f in files:
                st.write(f"- {f.name}")

            # zip and download
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, arcname=f.name)
            zip_buf.seek(0)
            st.download_button(label="下载所有结果 (ZIP)", data=zip_buf, file_name=zip_name, mime="application/zip")
