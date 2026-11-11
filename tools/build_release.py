"""Rebuild a deterministic ZIP and file manifest from the project checkout.

Run from anywhere: python tools/build_release.py
The manifest covers files within the source tree, not itself or the ZIP.
"""
from hashlib import sha256
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent.parent
out = root.parent / 'REI-1.0_v1.0.0.zip'
allow = {'.py', '.md', '.txt', '.json', '.toml', '.sha256'}
exclude_dirs = {'__pycache__', '.git', '.pytest_cache', 'build', 'dist', '.mypy_cache', '.venv', 'rei0_epistemic_graph.egg-info'}
items = sorted((p for p in root.rglob('*') if p.is_file() and
                not any(x in exclude_dirs for x in p.relative_to(root).parts) and
                (p.suffix in allow or p.name in {'.gitignore', 'LICENSE'})),
               key=lambda p:p.relative_to(root).as_posix())
items = [p for p in items if p.name != 'MANIFEST.sha256']
(root/'MANIFEST.sha256').write_text(''.join(sha256(p.read_bytes()).hexdigest()+'  '+
    p.relative_to(root).as_posix()+'\n' for p in items), encoding='utf-8')
items.append(root/'MANIFEST.sha256')
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for p in sorted(items, key=lambda p:p.relative_to(root).as_posix()):
        arcname = 'REI-1.0/'+p.relative_to(root).as_posix()
        info = zipfile.ZipInfo(arcname, date_time=(2026,11,10,19,30,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=(0o644 << 16)
        archive.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
print(f'{out} ({out.stat().st_size} bytes; {len(items)} files)')
print('SHA256:',sha256(out.read_bytes()).hexdigest())
