import sys
import traceback
from pathlib import Path

# simple CI test runner for processor
from processor import process_batch_files

def main():
    inp = Path('test_data')
    out = Path('test_out')
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    try:
        results_dir, summary = process_batch_files(str(inp), str(out), cp_value=200, force_density=None, generate_html=False)
        print("Results dir:", results_dir)
        print(summary.to_csv(index=False))
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        try:
            (out / 'ci_traceback.txt').write_text(tb)
        except Exception:
            pass
        sys.exit(1)

if __name__ == '__main__':
    main()
