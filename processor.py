# processor.py
from pathlib import Path
import re
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import plotly.express as px

def parse_zem_file(path: Path):
    txt = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    header_idx = None
    for i,l in enumerate(txt[:8]):
        if 'Measurement temp' in l or 'Measurement temp.' in l or 'Seebeck' in l:
            header_idx = i
            break
    if header_idx is None:
        header_idx = 1
    header = re.split(r'\t+|\s{2,}|\s+', txt[header_idx].strip())
    data_lines = txt[header_idx+1:]
    rows = []
    for ln in data_lines:
        if not ln.strip():
            continue
        parts = re.split(r'\t+|\s{2,}|\s+', ln.strip())
        rows.append(parts)
    if not rows:
        return {'sample': path.stem}, pd.DataFrame()
    df = pd.DataFrame(rows)
    if df.shape[1] == len(header):
        df.columns = [h.strip() for h in header]
    else:
        names = ['Measurement temp.(C)','Resistivity(Ohm m)','D.Volt./D.Temp.(V/K)',
                 'Wire seebeck(V/K)','Seebeck coeff.(V/K)','Power factor(W/m K^2)',
                 'Figure of merit(1/K)','Dark EMF(V)','R^2 by Seebeck','Sigma by  Seebeck']
        names = names[:df.shape[1]]
        df.columns = names
    for c in df.columns:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',','').str.strip(), errors='coerce')
    colmap = {}
    for c in df.columns:
        lc = c.lower()
        if 'temp' in lc:
            colmap[c] = 'T_C'
        elif 'resist' in lc:
            colmap[c] = 'resistivity_Ohm_m'
        elif 'power' in lc or 'powerfactor' in lc or 'pf' in lc:
            colmap[c] = 'PF_W_per_mK2'
        elif 'seebeck' in lc and 'wire' in lc:
            colmap[c] = 'wire_seebeck_V_per_K'
        elif 'seebeck' in lc:
            colmap[c] = 'Seebeck_V_per_K'
        elif 'figure' in lc or 'merit' in lc:
            colmap[c] = 'figure_of_merit_1_per_K'
        else:
            colmap[c] = c
    df = df.rename(columns=colmap)
    if 'Seebeck_V_per_K' in df.columns:
        s_med = df['Seebeck_V_per_K'].abs().median(skipna=True)
        if pd.notna(s_med) and s_med > 1.0:
            df['Seebeck_V_per_K'] = df['Seebeck_V_per_K'] * 1e-6
    if 'resistivity_Ohm_m' in df.columns:
        df['sigma_S_per_m_calc'] = 1.0 / df['resistivity_Ohm_m']
    metadata = {'sample': path.stem, 'source': str(path)}
    return metadata, df

def parse_lfa_file(path: Path):
    txt = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    metadata = {}
    results = []
    in_results = False
    for ln in txt:
        if ln.strip().startswith('##Results'):
            in_results = True
            continue
        if not in_results:
            m = re.match(r'#?([^,]+),\s*(.+)', ln)
            if m:
                k = m.group(1).strip()
                v = m.group(2).strip()
                metadata[k] = v
            continue
        else:
            if not ln.strip():
                continue
            parts = [p.strip() for p in ln.split(',') if p.strip()!='']
            if len(parts) >= 5:
                try:
                    shot = parts[0]
                    time_min = float(parts[1])
                    temp_C = float(parts[2])
                    alpha_mm2_s = float(parts[3])
                    std = float(parts[4])
                    results.append({'shot':shot,'time_min':time_min,'T_C':temp_C,
                                    'alpha_mm2_per_s':alpha_mm2_s,'alpha_std':std})
                except:
                    continue
    df = pd.DataFrame(results)
    if not df.empty:
        df['alpha_m2_per_s'] = df['alpha_mm2_per_s'] * 1e-6
    density = None
    for k,v in metadata.items():
        if 'density' in k.lower():
            try:
                density = float(v) * 1000.0
            except:
                pass
    return {'raw_meta':metadata,'density_kg_per_m3':density,'source':str(path)}, df

def parse_cp_file(cp_path: str):
    df = pd.read_csv(cp_path)
    tcol = next((c for c in df.columns if 't' in c.lower()), df.columns[0])
    cpcol = next((c for c in df.columns if 'p' in c.lower()), df.columns[1] if df.shape[1]>1 else df.columns[-1])
    xs = df[tcol].values
    if xs.max() < 200:
        xs = xs + 273.15
    ys = df[cpcol].values
    interp = interp1d(xs, ys, bounds_error=False, fill_value=(ys[0], ys[-1]))
    return lambda T_K: float(interp(T_K))

def compute_kappa_from_lfa(lfa_df, density_kg_m3, cp_func):
    df = lfa_df.copy()
    df['T_K'] = df['T_C'] + 273.15
    df['Cp'] = df['T_K'].apply(cp_func)
    df['kappa_W_per_mK'] = df['alpha_m2_per_s'] * density_kg_m3 * df['Cp']
    return df

def process_batch_files(input_dir: str, output_dir: str, cp_value: float=None, cp_file: str=None, force_density: float=None, generate_html: bool=True):
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    zem_files = []
    lfa_files = []
    for p in inp.iterdir():
        if p.is_file():
            txt = p.read_text(encoding='utf-8', errors='ignore')
            if 'Measurement temp' in txt or 'Seebeck' in txt:
                zem_files.append(p)
            if '##Results' in txt or 'Diffusivity' in txt or 'Thermal_diffusivity' in txt:
                lfa_files.append(p)
    if cp_file:
        cp_fn = parse_cp_file(cp_file)
    elif cp_value is not None:
        cp_fn = lambda T_K: float(cp_value)
    else:
        raise ValueError("cp_file or cp_value required")
    summary_rows = []
    for zem in zem_files:
        meta, zdf = parse_zem_file(zem)
        if zdf.empty:
            continue
        matched = None
        for lf in lfa_files:
            if meta.get('sample') and meta['sample'] in lf.name:
                matched = lf
                break
        if matched is None and lfa_files:
            matched = lfa_files[0]
        if matched is None:
            zdf.to_csv(out / (zem.stem + '_parsed.csv'), index=False)
            continue
        lmeta, ldf = parse_lfa_file(matched)
        density = force_density or lmeta.get('density_kg_per_m3')
        if density is None:
            raise ValueError(f"No density for LFA {matched.name}; provide force_density or ensure LFA header has Ref_density")
        kdf = compute_kappa_from_lfa(ldf, density, cp_fn)
        if 'T_C' not in zdf.columns:
            for c in zdf.columns:
                if 'temp' in c.lower():
                    zdf = zdf.rename(columns={c:'T_C'})
                    break
        zdf['T_K'] = zdf['T_C'] + 273.15
        if 'Seebeck_V_per_K' not in zdf.columns:
            for c in zdf.columns:
                if 'seebeck' in c.lower():
                    zdf = zdf.rename(columns={c:'Seebeck_V_per_K'})
                    break
        if 'sigma_S_per_m_calc' not in zdf.columns and 'resistivity_Ohm_m' in zdf.columns:
            zdf['sigma_S_per_m_calc'] = 1.0 / zdf['resistivity_Ohm_m']
        if 'sigma_S_per_m_calc' in zdf.columns:
            zdf['sigma_S_per_m'] = zdf['sigma_S_per_m_calc']
        else:
            zdf['sigma_S_per_m'] = np.nan
        zdf['PF_W_per_mK2_calc'] = (zdf['Seebeck_V_per_K'] ** 2) * zdf['sigma_S_per_m']
        interp_k = interp1d(kdf['T_K'].values, kdf['kappa_W_per_mK'].values, bounds_error=False, fill_value='extrapolate')
        zdf['kappa_W_per_mK'] = zdf['T_K'].apply(lambda t: float(interp_k(t)))
        zdf['ZT_calc'] = zdf['PF_W_per_mK2_calc'] * zdf['T_K'] / zdf['kappa_W_per_mK']
        zdf.to_csv(out / (zem.stem + '_processed.csv'), index=False)
        try:
            fig, ax = plt.subplots(figsize=(6,4))
            ax.plot(zdf['T_K'], zdf['ZT_calc'], marker='o')
            ax.set_xlabel('T (K)')
            ax.set_ylabel('ZT')
            ax.set_title(zem.stem + ' ZT vs T')
            fig.savefig(out / (zem.stem + '_ZT_vs_T.png'), dpi=200, bbox_inches='tight')
            plt.close(fig)
        except Exception:
            pass
        if generate_html:
            try:
                pfig = px.line(zdf, x='T_K', y=['ZT_calc','PF_W_per_mK2_calc','kappa_W_per_mK'],
                               labels={'value':'value','variable':'metric','T_K':'T (K)'},
                               title=zem.stem + ' metrics vs T')
                pfig.write_html(str(out / (zem.stem + '_metrics.html')))
            except Exception:
                pass
        summary_rows.append({
            'sample': zem.stem,
            'n_points': len(zdf),
            'max_ZT': float(zdf['ZT_calc'].max()) if zdf['ZT_calc'].notna().any() else np.nan,
            'mean_ZT': float(zdf['ZT_calc'].mean()) if zdf['ZT_calc'].notna().any() else np.nan
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(out / 'summary.csv', index=False)
    return str(out), summary_df
