Thermolectric data analysis (ZEM-3 + LFA) - Demo

Overview
- This project parses ZEM-3 style Seebeck/resistivity CSVs and LFA thermal diffusivity files,
  computes sigma, PF, kappa (using Cp and density), and ZT, then outputs processed CSVs and plots.

Quick demo (CLI batch run)
1. Create a working dir and save the project files.
2. Create Python venv (optional) and install deps:
   python -m venv venv
   source venv/bin/activate    # Linux / macOS
   venv\Scripts\activate       # Windows
   pip install -r requirements.txt

3. Ensure sample input files are in ./data (they are included in this repo).
4. Run the batch processor:
   python run_batch.py --input_dir data --output_dir out --cp_value 200 --force_density 7700

   - cp_value: Cp in J/kgK (you chose manual input)
   - force_density: density in kg/m3 (optional; if provided it overrides LFA header)

5. Outputs:
   - ./out/<sample>_processed.csv
   - ./out/<sample>_ZT_vs_T.png
   - ./out/<sample>_metrics.html
   - ./out/summary.csv

6. Create zip:
   zip -r results.zip out

Notes
- For web UI (Streamlit): run `streamlit run streamlit_app.py` then open http://localhost:8501
- If LFA files have Ref_density in header, you may omit --force_density; otherwise provide density (kg/m3).
- If you have a Cp vs T CSV, run with `--cp_file cp_table.csv` instead of --cp_value.
