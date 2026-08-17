# processor.py
# Parsing, unit conversion, merging and thermoelectric computations (ZT, PF, k components).
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

DEFAULT_LORRENZ = 2.44e-8  # W·Ω·K^-2

def _to_num(s):
    return pd.to_numeric(s, errors='coerce')

def parse_zem(path: Path) -> pd.DataFrame:
    txt = path.read_text(encoding='utf-8', errors='ignore')
    # try headered CSV/TSV with heuristics
    for sep in [',', '\t', r'\s+']:
        try:
            df = pd.read_csv(path, sep=sep, engine='python')
        except Exception:
            continue
        cols_l = [c.lower() for c in df.columns]
        cmap = {}
        for i, c in enumerate(cols_l):
            if 'temp' in c or 'temperature' in c or c.strip() == 't':
                cmap['T'] = df.columns[i]
            if 'seeb' in c or 'thermo' in c or 's (' in c or c.strip() == 's':
                cmap['S'] = df.columns[i]
            if 'resist' in c or 'rho' in c or c.strip() == 'res':
                cmap['rho'] = df.columns[i]
        if 'T' in cmap:
            out = pd.DataFrame()
            out['T'] = _to_num(df[cmap['T']])
            if 'S' in cmap:
                out['S'] = _to_num(df[cmap['S']])
            if 'rho' in cmap:
                out['rho'] = _to_num(df[cmap['rho']])
            out = out.dropna(subset=['T']).sort_values('T').reset_index(drop=True)
            if not out.empty:
                return out
    # fallback: numeric lines -> first 2-3 numeric cols as T,S,rho
    lines = [l for l in txt.splitlines() if any(ch.isdigit() for ch in l)]
    if not lines:
        return pd.DataFrame()
    from io import StringIO
    try:
        df = pd.read_csv(StringIO("\n".join(lines)), header=None, sep=r'\s+|,|\t', engine='python')
    except Exception:
        return pd.DataFrame()
    if df.shape[1] >= 2:
        out = pd.DataFrame()
        out['T'] = _to_num(df.iloc[:, 0])
        out['S'] = _to_num(df.iloc[:, 1]) if df.shape[1] > 1 else np.nan
        if df.shape[1] > 2:
            out['rho'] = _to_num(df.iloc[:, 2])
        out = out.dropna(subset=['T']).sort_values('T').reset_index(drop=True)
        return out
    return pd.DataFrame()

def parse_lfa(path: Path) -> pd.DataFrame:
    txt = path.read_text(encoding='utf-8', errors='ignore')
    lines = []
    for l in txt.splitlines():
        s = l.strip()
        if not s:
            continue
        if any(ch.isdigit() for ch in s) and (',' in s or '\t' in s or ' ' in s):
            lines.append(s)
    if not lines:
        return pd.DataFrame()
    from io import StringIO
    try:
        df = pd.read_csv(StringIO("\n".join(lines)), header=None, engine='python')
    except Exception:
        return pd.DataFrame()
    out = pd.DataFrame()
    if df.shape[1] >= 2:
        out['T'] = _to_num(df.iloc[:, 0])
        out['alpha'] = _to_num(df.iloc[:, 1])
    else:
        out['alpha'] = _to_num(df.iloc[:, 0])
    out = out.dropna(subset=['alpha']).reset_index(drop=True)
    return out

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
