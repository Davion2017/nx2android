# The release check: port games with the player's bundle, as a player would, and keep each result in docs/RELEASE_CHECK.md.
#   port_check.py <bundle folder> <game folder> [<game folder> …] [--home DIR] [--fresh] [--write]
# A game folder holds the game's NSP / XCI files: hard links to the real ones are enough (mklink /H, or ln in Git Bash), so a new folder gives a port
# from scratch without copying the game. The bundle runs with a player folder of its own (--home, default <bundle>/../home): its settings, signing key,
# translator and downloaded tools (`nx2android.exe -m porter tools --download` there first), so nothing from the developer's machine is used.
# --fresh deletes each folder's <title ID>_build first. --write puts each game's row in docs/RELEASE_CHECK.md, replacing that game's earlier row.
# Each port's events go to <game folder>/port_check.jsonl.
import argparse, datetime, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / 'docs/RELEASE_CHECK.md'
BEGIN, END = '<!-- port_check rows -->', '<!-- /port_check rows -->'


def size(p):
    p = Path(p)
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob('*') if f.is_file())


def port(exe, folder, env, fresh):
    if fresh:
        for b in folder.glob('*_build'): shutil.rmtree(b)
    log, events, t0 = folder / 'port_check.jsonl', [], time.time()
    with open(log, 'w', encoding='utf-8') as f:
        p = subprocess.Popen([str(exe), '-m', 'porter', 'port', str(folder), '--progress', 'json'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True, encoding='utf-8', errors='replace')
        for ln in p.stdout:
            f.write(ln)
            try: ev = json.loads(ln)
            except ValueError: ev = {'ev': 'say', 'msg': ln.rstrip()}
            events.append(ev)
            if ev.get('ev') == 'stage_end': print(f'  {"✓" if ev.get("ok", True) else "✗"} {ev["name"]} ({ev.get("elapsed", 0):.0f} s) {ev.get("summary", "")}', flush=True)
        rc = p.wait()
    res = next((e for e in reversed(events) if e.get('ev') == 'result'), None)
    red = [e['msg'].removeprefix('[RED] ') for e in events if e.get('ev') == 'say' and str(e.get('msg', '')).startswith('[RED] ')]
    return rc, res, red, time.time() - t0


def row(folder, ver, rc, res, red, took, fresh):
    when = datetime.date.today().isoformat()
    mins = f'{took / 60:.0f} min' + (' (from scratch)' if fresh else '')
    if rc == 0 and res:
        dlc = len(list((Path(res['data']) / 'aoc').glob('*'))) if (Path(res['data']) / 'aoc').is_dir() else 0
        out = f'APK {size(res["apk"]) / 2**20:.0f} MB, data {size(res["data"]) / 2**30:.1f} GB' + (f', {dlc} DLC' if dlc else '')
        warn = f' ({"; ".join(red)})' if red else ''
        return f'| {res["name"]} | `{res["title_id"]}` | {res["display"] or res["version"]} | ported{warn} | {out} | {mins} | {ver} | {when} |', res['title_id']
    tid = next(iter(re.findall(r'[0-9A-F]{16}', ' '.join(p.name for p in folder.glob('*.ns[pP]')))), '?')
    return f'| {folder.name} | `{tid}` | | **failed** (exit {rc}): {(red or ["no message"])[-1]} | | {mins} | {ver} | {when} |', tid


def write(rows):
    t = STATUS.read_text(encoding='utf-8')
    a, b = t.index(BEGIN) + len(BEGIN), t.index(END)
    have = [ln for ln in t[a:b].strip().splitlines() if ln.startswith('| ') and not ln.startswith('| Game') and not ln.startswith('|---')]
    keep = [ln for ln in have if not any(f'`{tid}`' in ln for _, tid in rows)]
    body = sorted(keep + [r for r, _ in rows], key=lambda ln: ln.split('|')[1].strip().lower())
    head = '| Game | Title ID | Version | Result | Output | Time | Bundle | Date |\n|---|---|---|---|---|---|---|---|'
    STATUS.write_text(t[:a] + '\n' + head + '\n' + '\n'.join(body) + '\n' + t[b:], encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description='port games with the player\'s bundle and record the results (docs/RELEASE_CHECK.md)')
    ap.add_argument('bundle', help='the unzipped bundle folder (nx2android.exe in it)'); ap.add_argument('folders', nargs='+')
    ap.add_argument('--home', help='the player folder the bundle uses (default: <bundle>/../home)')
    ap.add_argument('--fresh', action='store_true', help='delete each <title ID>_build first: a port from scratch')
    ap.add_argument('--write', action='store_true', help='put each row in docs/RELEASE_CHECK.md')
    a = ap.parse_args()
    bundle = Path(a.bundle).resolve(); exe = bundle / ('nx2android.exe' if os.name == 'nt' else 'nx2android')
    ver = (bundle / 'VERSION').read_text().strip() if (bundle / 'VERSION').is_file() else bundle.name
    env = dict(os.environ, NX2A_HOME=str(Path(a.home).resolve() if a.home else bundle.parent / 'home'), PYTHONIOENCODING='utf-8')
    doc = subprocess.run([str(exe), '-m', 'porter', 'doctor'], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if doc.returncode: sys.exit(f'the bundle\'s setup is not complete (NX2A_HOME={env["NX2A_HOME"]}):\n{doc.stdout}')
    rows, failed = [], 0
    for f in map(lambda p: Path(p).resolve(), a.folders):
        print(f'== {f.name}', flush=True)
        rc, res, red, took = port(exe, f, env, a.fresh)
        r = row(f, ver, rc, res, red, took, a.fresh); rows.append(r); failed += rc != 0
        print(r[0], flush=True)
    if a.write: write(rows); print(f'wrote {len(rows)} rows to {STATUS}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
