# processor.py
# Parsing, unit conversion, merging and thermoelectric computations (ZT, PF, k components).
import re
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

DEFAULT_LORRENZ = 2.44e-8  # W·Ω·K^-2

NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def _to_num(s):
    return pd.to_numeric(s, errors='coerce')


def _extract_numbers_from_line(line: str):
    return NUM_RE.findall(line)


def parse_zem(path: Path) -> pd.DataFrame:
    """
    Robust parser for common ZEM output formats.
    Strategy:
    - Scan the first ~200 lines for a header line containing keywords (temp, seeb, rho, resist).
    - Find the first numeric data line (at least 2 numbers).
    - Try reading with several separators, using header when found, otherwise as header=None and map columns by position.
    - Fall back to taking the first 2-3 numeric columns as T, S, rho.
    Returns DataFrame with columns 'T', 'S' and optionally 'rho' (numeric), or empty DataFrame on failure.
    """
    txt = path.read_text(encoding='utf-8', errors='ignore')
    lines = txt.splitlines()
    if not lines:
        return pd.DataFrame()

    # find header-like line (within top 200 lines)
    header_idx = None
    for i, line in enumerate(lines[:200]):
        l = line.lower()
        if any(k in l for k in ('temp', 'temperature', 'seeb', 'seebeck', 'thermopower', 'resist', 'rho')):
            header_idx = i
            break

    # find first numeric data line (anywhere)
    data_idx = None
    for i, line in enumerate(lines):
        nums = _extract_numbers_from_line(line)
        if len(nums) >= 2:
            data_idx = i
            break

    # decide start index: prefer header if it precedes data
    if header_idx is not None and (data_idx is None or header_idx <= data_idx):
        start_idx = header_idx
        header_present = True
    elif data_idx is not None:
        start_idx = data_idx
        header_present = False
    else:
        return pd.DataFrame()

    content = '\n'.join(lines[start_idx:])
    from io import StringIO

    # Try reading with a set of separators
    sep_options = [',', '\t', ';', r'\s+']
    for sep in sep_options:
        try:
            if header_present:
                df = pd.read_csv(StringIO(content), sep=sep, engine='python')
            else:
                # no header line; read as positional columns
                df = pd.read_csv(StringIO(content), header=None, sep=sep, engine='python')
        except Exception:
            continue
        if df is None or df.shape[0] == 0:
            continue
        # Normalize column names
        if header_present:
            cols = [str(c).strip() for c in df.columns]
            lower = [c.lower() for c in cols]
            colmap = {}
            for i, c in enumerate(lower):
                if 'temp' in c or 'temperature' in c or re.fullmatch(r't\b', c):
                    colmap['T'] = cols[i]
                if 'seeb' in c or 'seebeck' in c or 'thermopower' in c or (c.strip() == 's'):
                    colmap['S'] = cols[i]
                if 'resist' in c or 'rho' in c or c.strip() in ('res', 'resistivity'):
                    colmap['rho'] = cols[i]
            out = pd.DataFrame()
            if 'T' in colmap:
                out['T'] = _to_num(df[colmap['T']])
            if 'S' in colmap:
                out['S'] = _to_num(df[colmap['S']])
            if 'rho' in colmap:
                out['rho'] = _to_num(df[colmap['rho']])
            # If we found T (and maybe others) return
            if 'T' in out.columns and not out['T'].dropna().empty:
                out = out.dropna(subset=['T']).sort_values('T').reset_index(drop=True)
                return out
            # else continue trying other separators
        else:
            # headerless numeric table: pick numeric columns
            # ensure columns are numeric where possible
            num_df = df.apply(_to_num)
            # keep only numeric columns
            numeric_cols = [c for c in num_df.columns if pd.api.types.is_numeric_dtype(num_df[c])]
            if len(numeric_cols) >= 2:
                # Heuristic: choose first column that is monotonic increasing and within typical temp ranges as T
                chosen_T = None
                for c in numeric_cols[:3]:
                    col = num_df[c]
                    if col.dropna().empty:
                        continue
                    mn, mx = col.min(), col.max()
                    # typical temperature 0..1500 K heuristic
                    if 0 <= mn <= mx and (mn >= -50 and mx <= 2000):
                        # prefer columns that are mostly increasing
                        if col.is_monotonic_increasing or col.is_monotonic_decreasing:
                            chosen_T = c
                            break
                if chosen_T is None:
                    chosen_T = numeric_cols[0]
                # choose subsequent columns as S and rho if present
                idx = numeric_cols.index(chosen_T)
                # try to pick S as next numeric column
                s_col = None
                rho_col = None
                if idx + 1 < len(numeric_cols):
                    s_col = numeric_cols[idx + 1]
                if idx + 2 < len(numeric_cols):
                    rho_col = numeric_cols[idx + 2]
                out = pd.DataFrame()
                out['T'] = num_df[chosen_T]
                if s_col is not None:
                    out['S'] = num_df[s_col]
                if rho_col is not None:
                    out['rho'] = num_df[rho_col]
                out = out.dropna(subset=['T']).sort_values('T').reset_index(drop=True)
                return out
    # Final fallback: try to extract numeric tokens line-by-line and build columns
    rows = []
    for line in lines:
        nums = _extract_numbers_from_line(line)
        if len(nums) >= 2:
            rows.append([float(x) for x in nums[:3]])
    if rows:
        arr = np.array(rows)
        out = pd.DataFrame()
        out['T'] = _to_num(arr[:, 0])
        if arr.shape[1] >= 2:
            out['S'] = _to_num(arr[:, 1])
        if arr.shape[1] >= 3:
            out['rho'] = _to_num(arr[:, 2])
        out = out.dropna(subset=['T']).sort_values('T').reset_index(drop=True)
        return out

    return pd.DataFrame()
