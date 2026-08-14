# name=streamlit_app.py
import streamlit as st
import tempfile, zipfile, shutil, io
from pathlib import Path
import pandas as pd
import plotly.express as px
from processor import process_batch_files
import time

st.set_page_config(page_title="ThermoLab — 热电分析平台", page_icon="🌡️", layout="wide")

# --- Simple custom styling ---
st.markdown(
    """
    <style>
    .header {display:flex;align-items:center;gap:12px;}
    .title {font-size:28px;font-weight:700;}
    .subtitle {color: #6b7280; margin-top:4px;}
    .card {background-color: #ffffff; padding:12px; border-radius:8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);}
    .muted {color:#6b7280;font-size:13px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Top bar
with st.container():
    st.markdown('<div class="header"><div class="title">ThermoLab</div><div class="subtitle">热电材料 ZEM-3 & LFA 数据分析平台</div></div>', unsafe_allow_html=True)
    st.markdown("---")

# Layout: left controls, right main
left, right = st.columns([1, 2.2], gap="large")

with left:
    st.markdown("### 参数 & 上传")
    with st.expander("输入参数", expanded=True):
        cp_mode = st.radio("Cp 输入方式", ("常数 Cp (J/kgK)", "上传 Cp_vs_T CSV"), index=0)
        if cp_mode.startswith("常数"):
            cp_value = st.number_input("Cp 常数 (J/kgK)", value=200.0, format="%.3f")
            cp_file = None
        else:
            cp_file = st.file_uploader("上传 Cp_vs_T CSV (列: T, Cp)", type=["csv"])
            cp_value = None
        density_override = st.number_input("密度覆盖 (kg/m3)（可选）", value=0.0, format="%.2f")
        if density_override <= 0:
            density_override = None

    st.markdown("### 1) 上传文件（分别上传）")
    st.caption("请先分别上传 ZEM-3（Seebeck/Resistivity）与 LFA（热扩散率）文件。")
    zem_files = st.file_uploader("上传 ZEM 文件（可多选）", accept_multiple_files=True, key="zem_files")
    lfa_files = st.file_uploader("上传 LFA 文件（可多选）", accept_multiple_files=True, key="lfa_files")

    st.markdown("### 快速操作")
    auto_pair = st.button("自动按文件名建议配对")
    clear_uploads = st.button("清空上传并重选")

    st.markdown("---")
    st.markdown("帮助与示例")
    st.write("• 请确保 ZEM 文件名能包含样本标识；LFA 文件头含 Ref_density 或在侧栏输入密度。")
    st.markdown("• 本平台仅作数据分析示例，请勿上传敏感数据到公开部署。",unsafe_allow_html=True)

with right:
    # Workspace tabs
    tabs = st.tabs(["配对 & 选择", "运行 & 进度", "结果与下载", "日志"])
    pairing_tab, run_tab, results_tab, logs_tab = tabs

    # Prepare temp directory storage on upload
    if 'tmpdir' not in st.session_state:
        st.session_state.tmpdir = None
        st.session_state.upload_time = None
    if clear_uploads:
        st.session_state.tmpdir = None

    if (zem_files or lfa_files) and st.session_state.tmpdir is None:
        td = Path(tempfile.mkdtemp(prefix="thermo_"))
        zem_dir = td / "zem"; lfa_dir = td / "lfa"
        zem_dir.mkdir(parents=True, exist_ok=True); lfa_dir.mkdir(parents=True, exist_ok=True)
        for f in zem_files or []:
            (zem_dir / f.name).write_bytes(f.read())
        for f in lfa_files or []:
            (lfa_dir / f.name).write_bytes(f.read())
        st.session_state.tmpdir = str(td)
        st.session_state.upload_time = time.time()

    if st.session_state.tmpdir:
        td = Path(st.session_state.tmpdir)
        zem_dir = td / "zem"; lfa_dir = td / "lfa"
        zem_list = sorted([p.name for p in zem_dir.iterdir() if p.is_file()])
        lfa_list = sorted([p.name for p in lfa_dir.iterdir() if p.is_file()])
    else:
        zem_list = []; lfa_list = []

    # --- Pairing tab ---
    with pairing_tab:
        st.subheader("2) 配对 & 选择要处理的文件")
        if not zem_list and not lfa_list:
            st.info("请在左侧上传 ZEM 与 LFA 文件后在此页面进行配对与选择。")
        else:
            st.markdown("已上传：")
            cols_summary = st.columns([1,1])
            cols_summary[0].write(f"ZEM 文件：{len(zem_list)}")
            cols_summary[1].write(f"LFA 文件：{len(lfa_list)}")

            st.markdown("#### 文件列表预览")
            with st.expander("查看 ZEM 文件名", expanded=False):
                for z in zem_list: st.write(f"- {z}")
            with st.expander("查看 LFA 文件名", expanded=False):
                for l in lfa_list: st.write(f"- {l}")

            # pairing UI: build rows with selectboxes
            st.markdown("#### 为每个 ZEM 选择对应的 LFA（或保留空表示不强配）")
            pairing = {}
            default_lfas = ["(不强配)"] + lfa_list
            for z in zem_list:
                # restore prior selection if present in session_state
                key = f"pair_{z}"
                prior = st.session_state.get(key, "(不强配)")
                sel = st.selectbox(f"{z}", options=default_lfas, index=default_lfas.index(prior) if prior in default_lfas else 0, key=key)
                pairing[z] = sel if sel != "(不强配)" else None

            st.markdown("操作：")
            col_op = st.columns(3)
            if col_op[0].button("配对为第一个 LFA（快速示例）"):
                # naive bulk map: map all ZEM to first LFA
                for z in zem_list:
                    st.session_state[f"pair_{z}"] = lfa_list[0] if lfa_list else "(不强配)"
                st.experimental_rerun()
            if col_op[1].button("导出 pairing CSV"):
                # prepare CSV
                rows = [{"ZEM":z, "LFA": pairing.get(z) or ""} for z in zem_list]
                csv = pd.DataFrame(rows).to_csv(index=False).encode()
                st.download_button("下载 pairing.csv", data=csv, file_name="pairing.csv", mime="text/csv")
            if col_op[2].button("导入 pairing CSV（未来实现）"):
                st.info("导入功能可定制，如需我来实现请告诉我配对 CSV 格式样例。")

            st.markdown("提示：你可以用自动配对按钮尝试按文件名匹配（页面左侧）。")

    # --- Run tab ---
    with run_tab:
        st.subheader("3) 运行 & 实时进度")
        st.markdown("确认参数后，点击开始。运行时会展示每个样本的状态。")
        if st.button("开始批处理（仅处理上面配对的文件）"):
            if not st.session_state.tmpdir:
                st.error("未上传文件或会话过期，请重新上传。")
            else:
                # build input_selected dir
                sel_dir = Path(st.session_state.tmpdir) / "input_selected"
                if sel_dir.exists():
                    shutil.rmtree(sel_dir)
                sel_dir.mkdir(parents=True, exist_ok=True)
                # copy selected ZEMs and their paired LFAs (or include all LFAs as fallback)
                for z in zem_list:
                    shutil.copy(Path(st.session_state.tmpdir)/"zem"/z, sel_dir / z)
                # copy all LFAs (processor will try matching or you can copy only selected ones)
                for lf in lfa_list:
                    shutil.copy(Path(st.session_state.tmpdir)/"lfa"/lf, sel_dir / lf)
                # choose cp input
                cp_path = None
                cp_val = None
                if cp_mode.startswith("常数"):
                    cp_val = float(cp_value)
                else:
                    if cp_file is None:
                        st.error("请选择或上传 Cp_vs_T CSV")
                        st.stop()
                    else:
                        cp_path = str(sel_dir / "cp_table.csv")
                        (sel_dir / "cp_table.csv").write_bytes(cp_file.read())
                st.info("开始计算，进度可能需要几秒到几十秒（取决于样本数量）...")
                # call processor
                try:
                    results_dir, summary_df = process_batch_files(
                        input_dir=str(sel_dir),
                        output_dir=str(Path(st.session_state.tmpdir)/"out"),
                        cp_value=cp_val,
                        cp_file=cp_path,
                        force_density=density_override,
                        generate_html=True
                    )
                except Exception as e:
                    st.error(f"处理触发异常：{e}")
                    st.stop()
                else:
                    st.success("批处理完成")
                    st.session_state.last_results = str(results_dir)
                    st.session_state.last_summary = summary_df.to_dict(orient="records")

        # Display per-sample statuses if available
        if st.session_state.get("last_summary"):
            st.markdown("运行状态：")
            df = pd.DataFrame(st.session_state.last_summary)
            st.dataframe(df)

    # --- Results tab ---
    with results_tab:
        st.subheader("4) 结果预览与下载")
        if not st.session_state.get("last_results"):
            st.info("尚无结果。请先在“运行 & 实时进度”页执行批处理。")
        else:
            outp = Path(st.session_state.last_results)
            files = sorted(outp.glob("*"))
            st.write(f"输出文件夹：{outp}；共 {len(files)} 个文件")
            # show summary table
            sum_csv = outp / "summary.csv"
            if sum_csv.exists():
                sdf = pd.read_csv(sum_csv)
                st.markdown("#### 汇总表")
                st.dataframe(sdf)
            st.markdown("#### 单样本文件")
            for f in files:
                st.write(f"- {f.name}")
            # offer ZIP download
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, arcname=f.name)
            zip_buf.seek(0)
            st.download_button("下载所有结果 (ZIP)", data=zip_buf, file_name="thermo_results.zip", mime="application/zip")

            # interactive plot for first processed file if present
            processed = [p for p in files if p.name.endswith("_processed.csv")]
            if processed:
                df0 = pd.read_csv(processed[0])
                if 'T_K' in df0.columns and 'ZT_calc' in df0.columns:
                    st.markdown("#### 交互式 ZT 曲线（示例：第一个 processed 文件）")
                    fig = px.line(df0, x='T_K', y='ZT_calc', title=processed[0].name)
                    st.plotly_chart(fig, use_container_width=True)

    # --- Logs tab ---
    with logs_tab:
        st.subheader("运行日志 & 错误追踪")
        if not st.session_state.get("last_results"):
            st.info("暂无日志文件。")
        else:
            outp = Path(st.session_state.last_results)
            errs = list(outp.glob("*_error.txt"))
            if errs:
                for e in errs:
                    st.markdown(f"**错误文件：{e.name}**")
                    st.code(e.read_text(), language="text")
            else:
                st.info("未检测到样本级 error 文本。若运行失败请查看 Streamlit 后端日志。")
