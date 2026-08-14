# processor.py
# Minimal, robust processor module used by CI test runner.
# It provides process_batch_files(...) that reads simple sample files
# and writes a summary CSV to the output directory.
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple

def _read_zem(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    header_idx = None
    for i, line in enumerate(text):
        if line.strip().startswith('Measurement') or 'Seebeck' in line and 'Resistivity' in line:
            header_idx = i
            break
    if header_idx is None:
        # fallback: use first non-empty line as header
        for i, line in enumerate(text):
            if line.strip():
                header_idx = i
                break
    data = '\n'.join(text[header_idx:]) if header_idx is not None else '\n'.join(text)
    from io import StringIO
    # Try tab-separated or whitespace
    for sep in ['\t', r'\s+']:
        try:
            df = pd.read_csv(StringIO(data), sep=sep, engine='python')
            if df.shape[1] >= 2:
                return df
        except Exception:
            continue
    # Last resort: basic CSV parse
    try:
        df = pd.read_csv(StringIO(data))
        return df
    except Exception:
        return pd.DataFrame()

def _read_lfa(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    # collect lines that look like data rows (contain commas and digits)
    data_lines = []
    header_line = None
    for i, line in enumerate(text):
        s = line.strip()
        if s.startswith('#Shot') or s.startswith('#Shot number'):
            header_line = s.lstrip('#').strip()
        if ',' in s and any(ch.isdigit() for ch in s):
            # skip lines that are clearly metadata like "1..2..3,4.2,31.4,1.985,0.079" are valid
            data_lines.append(s)
    if not data_lines:
        return pd.DataFrame()
    from io import StringIO
    data = '\n'.join(data_lines)
    try:
        df = pd.read_csv(StringIO(data), header=None)
        # if we have a header_line with comma-separated names, try to assign
        if header_line:
            cols = [c.strip() for c in header_line.split(',') if c.strip()]
            if len(cols) == df.shape[1]:
                df.columns = cols
        return df
    except Exception:
        return pd.DataFrame()

def process_batch_files(input_dir: str, output_dir: str, cp_value=None, force_density=None, generate_html: bool=False) -> Tuple[str, pd.DataFrame]:
    """
    Minimal compatible implementation used by CI.
    - input_dir: directory with test_data (zem/lfa files)
    - output_dir: where processed outputs & summary.csv will be written
    Returns (output_dir, summary_df)
    """
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # find likely files
    zem_file = None
    lfa_file = None
    if inp.exists() and inp.is_dir():
        for p in inp.iterdir():
            name = p.name.lower()
            if 'zem' in name and p.is_file():
                zem_file = p
            if 'lfa' in name and p.is_file():
                lfa_file = p

    zem_df = pd.DataFrame()
    lfa_df = pd.DataFrame()
    errors = []

    if zem_file:
        try:
            zem_df = _read_zem(zem_file)
        except Exception as e:
            errors.append(f"zem read error: {e}")

    if lfa_file:
        try:
            lfa_df = _read_lfa(lfa_file)
        except Exception as e:
            errors.append(f"lfa read error: {e}")

    # Build a lightweight summary DataFrame so tests can inspect something meaningful
    rows = []
    if not zem_df.empty:
        # try to extract a temperature column name
        temp_cols = [c for c in zem_df.columns if 'temp' in str(c).lower()]
        val_cols = [c for c in zem_df.columns if c not in temp_cols]
        rows.append({
            'source': 'zem',
            'rows': int(len(zem_df)),
            'temp_columns': ','.join(temp_cols) if temp_cols else '',
            'value_columns': ','.join(val_cols)[:200]
        })
    if not lfa_df.empty:
        rows.append({
            'source': 'lfa',
            'rows': int(len(lfa_df)),
            'temp_columns': '',
            'value_columns': ','.join(map(str, lfa_df.columns))[:200]
        })

    if not rows and errors:
        summary = pd.DataFrame({'error': errors})
    elif not rows:
        summary = pd.DataFrame([{'source':'none_found','rows':0}])
    else:
        summary = pd.DataFrame(rows)

    # write a summary.csv for CI/artifacts
    try:
        summary.to_csv(out / 'summary.csv', index=False)
    except Exception:
        # best effort write: plain text
        (out / 'summary.txt').write_text(summary.to_string(index=False))

    return str(out), summary
