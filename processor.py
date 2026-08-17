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


def parse_lfa(path: Path) -> pd.DataFrame:
    txt = path.read_text(encoding='utf-8', errors='ignore')
    lines = txt.splitlines()
    if not lines:
        return pd.DataFrame()

    header_line = None
    data_lines = []
    # search for header-like commented line (starts with #) that contains keywords
    for line in lines:
        s = line.strip()
        if s.startswith('#'):
            lower = s.lower()
            if 'temperature' in lower or 'diffus' in lower or 'shot' in lower:
                # remove leading '#'s and possible leading labels
                header_line = s.lstrip('#').strip()
        if any(ch.isdigit() for ch in s) and (',' in s or '\t' in s):
            data_lines.append(s)

    from io import StringIO
    try:
        if header_line and data_lines:
            # attempt to build CSV with header + data
            combined = header_line + '\n' + '\n'.join(data_lines)
            df = pd.read_csv(StringIO(combined), sep=',', engine='python')
            # map possible header names to T and alpha
            cols_l = [c.lower() for c in df.columns]
            t_col = None
            a_col = None
            for i, c in enumerate(cols_l):
                if 'temp' in c:
                    t_col = df.columns[i]
                if 'diff' in c or 'diffus' in c:
                    a_col = df.columns[i]
            out = pd.DataFrame()
            if t_col:
                out['T'] = _to_num(df[t_col])
            if a_col:
                out['alpha'] = _to_num(df[a_col])
            # if alpha present but T missing, try to find T in another column
            if 'alpha' in out.columns and 'T' not in out.columns:
                # try to find numeric column in df that looks like temperature
                for i, c in enumerate(df.columns):
                    colnum = _to_num(df[c])
                    mn, mx = colnum.min(), colnum.max()
                    if not colnum.dropna().empty and (mn >= -50 and mx <= 2000):
                        out['T'] = colnum
                        break
            out = out.dropna(subset=['alpha']).reset_index(drop=True)
            return out
        else:
            # fallback: parse numeric data lines without header
            if not data_lines:
                return pd.DataFrame()
            df = pd.read_csv(StringIO('\n'.join(data_lines)), header=None)
            num_df = df.apply(_to_num)
            # Heuristic: Temperature likely in a column with values in 0..2000 and alpha in mm2/s typical ~0.1..100
            t_col = None
            a_col = None
            for c in num_df.columns:
                col = num_df[c]
                if col.dropna().empty:
                    continue
                mn, mx = col.min(), col.max()
                if t_col is None and (mn >= -50 and mx <= 2000) and (col.is_monotonic_increasing or col.is_monotonic_decreasing):
                    t_col = c
                # diffusivity guess: values typically between 0.001 and 100 (mm2/s)
                if a_col is None and (mn > 0) and (mn >= 1e-4 and mx <= 1e4):
                    a_col = c
            out = pd.DataFrame()
            if t_col is not None:
                out['T'] = num_df[t_col]
            # try commonly the temperature is third column in LFA results, diffusivity fourth
            if a_col is None and num_df.shape[1] >= 4:
                a_col = 3
            if a_col is not None:
                out['alpha'] = num_df[a_col]
            # As final fallback, if shape[1]>=3, take column 2 as temperature and 3 as alpha
            if 'T' not in out.columns and num_df.shape[1] >= 3:
                out['T'] = num_df[2]
            if 'alpha' not in out.columns and num_df.shape[1] >= 4:
                out['alpha'] = num_df[3]
            out = out.dropna(subset=['alpha']).reset_index(drop=True)
            return out
    except Exception:
        return pd.DataFrame()


def convert_units(df: pd.DataFrame,
                  s_unit: str = 'uV/K',
                  rho_unit: str = 'mohm_cm',
                  alpha_unit: str = 'mm2/s') -> pd.DataFrame:
    out = df.copy()
    if 'S' in out.columns:
        if s_unit == 'uV/K':
            out['S_V'] = out['S'] * 1e-6
            out['S_uV'] = out['S']
        else:
            out['S_V'] = out['S']
            out['S_uV'] = out['S'] * 1e6
    if 'rho' in out.columns:
        if rho_unit == 'mohm_cm':
            out['rho_ohm_m'] = out['rho'] * 1e-5
        elif rho_unit == 'ohm_cm':
            out['rho_ohm_m'] = out['rho'] * 1e-2
        else:
            out['rho_ohm_m'] = out['rho']
    if 'alpha' in out.columns:
        if alpha_unit == 'mm2/s':
            out['alpha_m2_s'] = out['alpha'] * 1e-6
        else:
            out['alpha_m2_s'] = out['alpha']
    return out


def compute_thermo(zem: pd.DataFrame,
                   lfa: Optional[pd.DataFrame],
                   cp: float,
                   density: float,
                   s_unit: str = 'uV/K',
                   rho_unit: str = 'mohm_cm',
                   alpha_unit: str = 'mm2/s',
                   lorenz: float = DEFAULT_LORRENZ,
                   merge_tol_K: float = 2.0) -> pd.DataFrame:
    if zem is None or zem.empty:
        raise ValueError("ZEM data required")
    zem = zem.copy()
    lfa = lfa.copy() if (lfa is not None) else pd.DataFrame()
    zem = convert_units(zem, s_unit=s_unit, rho_unit=rho_unit, alpha_unit=alpha_unit)
    if not lfa.empty:
        lfa = convert_units(lfa, s_unit=s_unit, rho_unit=rho_unit, alpha_unit=alpha_unit)
    zem = zem.sort_values('T').reset_index(drop=True)
    merged = zem[['T']].copy()
    if 'S_V' in zem.columns:
        merged['S_V'] = zem['S_V']
        merged['S_uV'] = zem.get('S_uV', zem['S_V'] * 1e6)
    if 'rho_ohm_m' in zem.columns:
        merged['rho_ohm_m'] = zem['rho_ohm_m']
    # merge or fill alpha
    if not lfa.empty and 'alpha_m2_s' in lfa.columns:
        if 'T' in lfa.columns and not lfa['T'].isnull().all():
            lfa_s = lfa.sort_values('T').reset_index(drop=True)
            merged = pd.merge_asof(merged.sort_values('T'), lfa_s[['T','alpha_m2_s']].sort_values('T'),
                                   left_on='T', right_on='T', direction='nearest', tolerance=merge_tol_K)
        else:
            merged['alpha_m2_s'] = lfa['alpha_m2_s'].mean()
    else:
        merged['alpha_m2_s'] = np.nan
    # computations
    merged['sigma'] = 1.0 / merged['rho_ohm_m'].replace({0: np.nan}) if 'rho_ohm_m' in merged.columns else np.nan
    merged['PF'] = (merged.get('S_V', np.nan) ** 2) * merged['sigma']
    merged['k_l'] = cp * density * merged['alpha_m2_s']
    merged['k_e'] = lorenz * merged['sigma'] * merged['T']
    merged['k_total'] = merged['k_l'].fillna(0) + merged['k_e'].fillna(0)
    # avoid zero division
    merged['ZT'] = (merged.get('S_V', np.nan) ** 2) * merged['sigma'] * merged['T'] / merged['k_total'].replace({0: np.nan})
    # prepare output
    out = pd.DataFrame()
    out['T'] = merged['T']
    if 'S_uV' in merged.columns:
        out['S_uV_per_K'] = merged['S_uV']
    if 'S_V' in merged.columns:
        out['S_V_per_K'] = merged['S_V']
    if 'rho_ohm_m' in merged.columns:
        out['rho_ohm_m'] = merged['rho_ohm_m']
    out['sigma_S_per_m'] = merged['sigma']
    out['PF_W_per_mK2'] = merged['PF']
    out['k_e_W_per_mK'] = merged['k_e']
    out['k_l_W_per_mK'] = merged['k_l']
    out['k_total_W_per_mK'] = merged['k_total']
    out['ZT'] = merged['ZT']
    out['alpha_m2_per_s'] = merged.get('alpha_m2_s', np.nan)
    return out

def export_origin_csv(df: pd.DataFrame, path: Path, float_format: str = '%.6g'):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format=float_format)
    return path
