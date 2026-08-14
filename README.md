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
Run locally / tests
Run Streamlit UI locally:

pip install -r requirements.txt
streamlit run streamlit_app.py
Run unit tests:

pip install -r requirements.txt
pip install pytest
pytest -q
CI:

The repository includes a GitHub Actions workflow (.github/workflows/ci-test.yml) which runs tests and always uploads test_out artifacts for inspection.

在 Commit 区：

选择/输入分支： add-all-fixes（不要提交到 main）
Commit message： docs: add run/test instructions
点击 Commit changes
当你完成后在这里回复「完成 README」。

创建 Pull Request（你要做）
进入仓库 → Pull requests → New pull request
base: main ， compare: add-all-fixes → Create pull request
填写（建议）：
Title: fix: clean processor, add simplified Streamlit UI, CI improvements and tests
Description: 简短说明改动点，例如：
Cleaned processor.py (removed patch markers, robust parsing)
Added simplified Streamlit UI (streamlit_app.py)
Improved CI workflow (PYTHONPATH, upload artifacts)
Added basic unit tests (tests/test_processor.py) and README instructions
点击 Create pull request
等 CI 运行并把结果发给我（你要做，然后把输出粘到这里）
打开 PR 页面或 Actions → 找最新的 CI run（CI Test）
等跑完然后把以下之一粘给我：
如果成功：右侧 Artifacts → 下载 test_out.zip → 解压并把 test_out/summary.csv 的全部文本粘到这里（或直接把 Run processor test 的控制台输出粘来）。
如果失败：展开 Jobs → test → Run processor test → 复制从 "Traceback (most recent call last):" 开始到最后一行的完整 traceback 并粘到这里。若有 artifact test_out/ci_traceback.txt 也下载并粘出它的内容。
我接下来会做的（我会在你把 CI 输出贴过来后继续）

读取 CI 输出（artifact 或 traceback），诊断并修复剩余问题（如果有）。
准备合并建议或直接把进一步修复做成新的 PR（视你是否要我直接写入；我可能仍需要写权限）。
如果你想我在创建 PR 后立刻去查看 CI 结果并继续修复，请在这里贴上 PR 链接或把 CI 的运行结果粘过来。现在先把 README 提交完并回复「完成 README」。
