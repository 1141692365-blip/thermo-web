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

粘贴完怎样保存
保存很简单，我把精确步骤写得一步步的——按你当前是在编辑 README 的页面操作。

如果你是在编辑已有文件（README.md）

编辑器里粘好内容后，往页面下滚到 Commit changes 区块。
在 “Commit changes” 区：
点击分支下拉（默认会显示 “Commit directly to main” 或当前分支），把它改成/选择 add-all-fixes。
如果下拉里看不到 add-all-fixes，可以直接在下拉输入框里键入 add-all-fixes，然后选择 “Create branch: add-all-fixes” 或 “Commit to add-all-fixes”。
在 “Commit message” 输入框写一句（例如）：docs: add run/test instructions
（可选）在下面的大文本框写更详细的说明。
点击右下角的绿色按钮 Commit changes（按钮上会显示 “Commit changes” 或 “Propose changes” 取决于分支选择）。
页面会刷新并显示你已把更改提交到 add-all-fixes 分支。
如果你是在新建文件（Create new file）

在“Create new file”页面把文件名填好并粘内容。
在页面下方的 Commit 区，把分支选择成 add-all-fixes（或直接在下拉创建该分支）。
填 Commit message 并点 Commit changes。
常见问题与错误提示

如果点 Commit 后出现 “You don’t have permission” 或类似错误：说明你当前的 GitHub 登录没有该仓库的写权限。把错误原文贴给我，我会告诉你下一步（通常改为在本地用脚本提交，或让有权限的人合并）。
如果 Commit 后 Actions 里显示 YAML 错误（Invalid workflow file）：把错误信息（GitHub 给的错误行号和消息）粘过来，我会帮你定位并修复。
下一步（提交后）

提交成功后在这里回复「完成 README」。
然后你可以创建 Pull Request（PR）：
仓库页面 → Pull requests → New pull request
base: main，compare: add-all-fixes → Create pull request → 填标题/描述 → Create pull request
创建 PR 会触发 CI；等跑完把 artifact（test_out/summary.csv）或运行日志粘给我，我会继续修复或合并建议。
需要我现在指导你创建 PR 吗？如果你已经保存了 README，请回复「完成 README」。
