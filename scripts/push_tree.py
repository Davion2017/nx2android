# Push a local directory tree to the device, skipping files already there at the same size; one adb push per directory batch
# so a wedged transfer costs little and a rerun resumes.   push_tree.py <local dir> <remote dir> [--batch-mb N]
import os, subprocess, sys, shlex
ADB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools', 'platform-tools', 'adb.exe')
local, remote = sys.argv[1], sys.argv[2].rstrip('/')
batch_mb = int(sys.argv[sys.argv.index('--batch-mb') + 1]) if '--batch-mb' in sys.argv else 256

r = subprocess.run([ADB, 'shell', f'[ -d {shlex.quote(remote)} ] && cd {shlex.quote(remote)} && find . -type f -exec stat -c "%s %n" {{}} +'], capture_output=True, text=True, errors='replace')
have = {}
for ln in r.stdout.splitlines():
    sz, _, name = ln.partition(' ')
    if sz.isdigit(): have[name[2:] if name.startswith('./') else name] = int(sz)

todo = []
for d, _, fs in os.walk(local):
    for f in fs:
        p = os.path.join(d, f); rel = os.path.relpath(p, local).replace(os.sep, '/')
        if have.get(rel) != os.path.getsize(p): todo.append((rel, os.path.getsize(p)))
total = sum(s for _, s in todo)
print(f'{len(todo)} files to push, {total / 1e6:.0f} MB ({len(have)} already on the device)', flush=True)

dirs = sorted({os.path.dirname(r) for r, _ in todo})
for d in dirs:
    subprocess.run([ADB, 'shell', 'mkdir', '-p', f'{remote}/{d}' if d else remote], check=True)
done = 0; batch = []; bsz = 0
def flush():
    global batch, bsz, done
    if not batch: return
    # adb push of several files into one remote directory; group by directory
    by = {}
    for rel, s in batch: by.setdefault(os.path.dirname(rel), []).append(rel)
    for d, rels in by.items():
        for i in range(0, len(rels), 64):
            part = rels[i:i + 64]
            print(f'  pushing {len(part)} file(s) to {d or "."}: {", ".join(os.path.basename(x) for x in part[:3])}{" ..." if len(part) > 3 else ""} '
                  f'({sum(os.path.getsize(os.path.join(local, x.replace("/", os.sep))) for x in part) / 1e6:.0f} MB)', flush=True)
            args = [ADB, 'push'] + [os.path.join(local, x.replace('/', os.sep)) for x in part] + [f'{remote}/{d}/' if d else f'{remote}/']
            rr = subprocess.run(args, capture_output=True, text=True, errors='replace')
            if rr.returncode: print(rr.stdout[-400:], rr.stderr[-400:]); sys.exit(1)
    done += bsz; print(f'  {done / 1e6:.0f}/{total / 1e6:.0f} MB', flush=True); batch = []; bsz = 0
for rel, s in todo:
    batch.append((rel, s)); bsz += s
    if bsz >= batch_mb << 20: flush()
flush(); print('ok')
