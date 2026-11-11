"""Verify source file checksums in an extracted REI release (stdlib only)."""
from hashlib import sha256
from pathlib import Path

root = Path(__file__).resolve().parent.parent
manifest = root / 'MANIFEST.sha256'
lines = manifest.read_text(encoding='utf-8').splitlines()
for line in lines:
    expected, sep, path = line.partition('  ')
    if not sep or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise SystemExit('Malformed manifest line')
    relative = Path(path)
    target = (root / relative).resolve()
    if relative.is_absolute() or root.resolve() not in target.parents or not target.is_file():
        raise SystemExit(f'Unsafe or missing manifest path: {path}')
    actual = sha256(target.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f'Hash mismatch: {path}')
print(f'OK: {len(lines)} release files match MANIFEST.sha256')
