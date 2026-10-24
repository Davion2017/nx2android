# Push a local tree to the device in short transfers: small files in batches, large files as 64 MB pieces that the device joins with dd.
# A stalled USB link costs one piece, and a rerun resumes (files already at the right size are skipped, pieces already in place are kept).
#   push_chunked.py <local dir or file> <remote dir or file> [--chunk-mb N] [--timeout S]
import os, subprocess, sys, shlex, time
ADB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'platform-tools', 'adb.exe')
args = [x for x in sys.argv[1:] if not x.startswith('--')]
opt = lambda k, d: int(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
local, remote = args[0], args[1].rstrip('/')
CHUNK = opt('--chunk-mb', 64) << 20; TMO = opt('--timeout', 120)

def adb(*a, tmo=TMO):
    for attempt in range(3):
        try:
            r = subprocess.run([ADB, *a], capture_output=True, text=True, errors='replace', timeout=tmo)
            if r.returncode == 0: return r.stdout
            err = (r.stdout + r.stderr).strip()[-300:]
        except subprocess.TimeoutExpired: err = f'timed out after {tmo}s'
        print(f'    adb {a[0]} failed ({err}), retry {attempt + 1}', flush=True)
        subprocess.run([ADB, 'wait-for-device'], timeout=300); time.sleep(2)
    sys.exit(f'adb {a[0]} failed 3 times; the device link is down')

def remote_sizes(rdir):
    out = adb('shell', f'[ -d {shlex.quote(rdir)} ] && cd {shlex.quote(rdir)} && find . -type f -exec stat -c "%s %n" {{}} + ; true')
    have = {}
    for ln in out.splitlines():
        sz, _, name = ln.partition(' ')
        if sz.isdigit(): have[name[2:] if name.startswith('./') else name] = int(sz)
    return have

if os.path.isfile(local): files = [(os.path.basename(remote), local)]; remote = os.path.dirname(remote)
else: files = [(os.path.relpath(os.path.join(d, f), local).replace(os.sep, '/'), os.path.join(d, f)) for d, _, fs in os.walk(local) for f in fs]
have = remote_sizes(remote)
todo = [(rel, p, os.path.getsize(p)) for rel, p in files if have.get(rel) != os.path.getsize(p) and not rel.startswith('.dmpart/')]
total = sum(s for _, _, s in todo); done = 0; t0 = time.time()
print(f'{len(todo)} files to push, {total / 1e6:.0f} MB ({len(files) - len(todo)} already on the device)', flush=True)
for d in sorted({os.path.dirname(r) for r, _, _ in todo}): adb('shell', 'mkdir', '-p', f'{remote}/{d}' if d else remote)

def progress(note):
    el = time.time() - t0; rate = done / el / 1e6 if el > 0 else 0
    print(f'  {done / 1e6:.0f}/{total / 1e6:.0f} MB, {rate:.1f} MB/s - {note}', flush=True)

small = [(r, p, s) for r, p, s in todo if s <= CHUNK]
for i in range(0, len(small), 32):   # small files: up to 32 per push into one directory each
    part = small[i:i + 32]; by = {}
    for r, p, s in part: by.setdefault(os.path.dirname(r), []).append(p)
    for d, ps in by.items(): adb('push', '-Z', *ps, f'{remote}/{d}/' if d else f'{remote}/')
    done += sum(s for _, _, s in part); progress(f'{len(part)} small files')

for rel, p, size in [(r, p, s) for r, p, s in todo if s > CHUNK]:
    dst = f'{remote}/{rel}'; pdir = f'{remote}/.dmpart'; n = (size + CHUNK - 1) // CHUNK
    adb('shell', 'mkdir', '-p', pdir); pieces = remote_sizes(pdir)
    print(f'  {rel}: {size / 1e6:.0f} MB in {n} pieces', flush=True)
    with open(p, 'rb') as f:
        for k in range(n):
            want = min(CHUNK, size - k * CHUNK); name = f'{k:04d}'
            if pieces.get(name) != want:
                tmp = os.path.join(os.environ.get('TEMP', '.'), 'dmpart.bin')
                f.seek(k * CHUNK); open(tmp, 'wb').write(f.read(want))
                adb('push', '-Z', tmp, f'{pdir}/{name}')
            done += want; progress(f'{os.path.basename(rel)} piece {k + 1}/{n}')
    q = shlex.quote(dst)   # join the pieces in order, then check the size
    adb('shell', f'rm -f {q} && for x in $(ls {pdir} | sort); do cat {pdir}/$x >> {q} || exit 1; done && rm -rf {pdir} && stat -c %s {q}', tmo=600)
    got = int(adb('shell', 'stat', '-c', '%s', dst).strip())
    if got != size: sys.exit(f'{rel}: {got} bytes on the device, expected {size}')
print('ok', flush=True)
