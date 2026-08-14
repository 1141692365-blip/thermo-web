import pytest
from pathlib import Path
from processor import _read_zem, _read_lfa, process_batch_files
import tempfile
import shutil

BASE = Path('test_data')

def test_read_zem_exists():
    zem = BASE / 'sample_zem.txt'
    assert zem.exists()
    df = _read_zem(zem)
    assert not df.empty
    assert any('temp' in str(c).lower() for c in df.columns)

def test_read_lfa_exists():
    lfa = BASE / 'sample_lfa.txt'
    assert lfa.exists()
    df = _read_lfa(lfa)
    assert not df.empty

def test_process_batch_files_creates_summary(tmp_path):
    # copy test_data into tmp input dir
    inp = tmp_path / 'in'
    out = tmp_path / 'out'
    inp.mkdir()
    out.mkdir()
    shutil.copy(Path('test_data/sample_zem.txt'), inp / 'sample_zem.txt')
    shutil.copy(Path('test_data/sample_lfa.txt'), inp / 'sample_lfa.txt')
    results_dir, summary = process_batch_files(str(inp), str(out))
    assert Path(results_dir).exists()
    assert not summary.empty
    assert (Path(results_dir) / 'summary.csv').exists()
