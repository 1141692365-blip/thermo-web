# streamlit_app.py (simplified UI)
import streamlit as st
import pandas as pd
from pathlib import Path
from processor import process_batch_files
import tempfile

st.set_page_config(page_title="Thermo Processor", layout="wide")

st.title("Thermo Data Processor")

st.sidebar.header("Upload / Settings")
uploaded = st.sidebar.file_uploader("Upload ZEM or LFA file(s)", accept_multiple_files=True)
cp_value = st.sidebar.number_input("Cp value (for processing)", value=200)
force_density = st.sidebar.text_input("Force density (optional)", value="")

if st.sidebar.button("Process uploaded files"):
    if not uploaded:
        st.sidebar.error("Please upload at least one file.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                dest = input_dir / f.name
                dest.write_bytes(f.read())
            out_dir = Path(tmp) / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                results_dir, summary = process_batch_files(str(input_dir), str(out_dir), cp_value=cp_value, force_density=None)
                st.success("Processing complete")
                st.subheader("Summary")
                st.dataframe(summary)
                summary_path = Path(results_dir) / "summary.csv"
                if summary_path.exists():
                    with open(summary_path, "rb") as fh:
                        st.download_button("Download summary.csv", fh, file_name="summary.csv")
                st.subheader("Output files")
                files = list(Path(results_dir).iterdir())
                if files:
                    for p in files:
                        st.write(f"- {p.name}")
            except Exception as e:
                st.error(f"Processing failed: {e}")

st.markdown("---")
st.info("Upload ZEM and/or LFA files from the sidebar, then click 'Process uploaded files'.")
