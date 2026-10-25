# adb for installing a port: the device list, installing the APK, and pushing the data pack in short transfers. Big pushes over one adb connection wedge adbd on some
# devices (a 6 GB RomFS), so small files go in batches and big files in 64 MB pieces that the device joins; a rerun resumes (files already at their size are skipped,
# pieces already in place are kept). Pushes use -Z: compressing them took adbd down.
import contextlib, hashlib, os, shlex, shutil, subprocess, tempfile, time
from pathlib import Path


class AdbError(Exception):
    pass


LONG_PATH = 240   # adb.exe is not long-path aware: it cannot open a file whose full path passes Windows' 260 characters (Viractal's Unity bundles in a deep game folder)


@contextlib.contextmanager
def short_paths(paths):
    """The files under paths adb can open: as they are, or (on Windows, when one is too long) hard links with the same names in a short temporary folder, so they
    keep their names on the device"""
    if os.name != 'nt' or all(len(str(Path(p).resolve())) < LONG_PATH for p in paths):
        yield [str(p) for p in paths]; return
    with tempfile.TemporaryDirectory(prefix='nx2a_') as t:
        out = []
        for p in paths:
            q = Path(t) / Path(p).name
            try: os.link(p, q)
            except OSError: shutil.copy2(p, q)
            out.append(str(q))
        yield out


class Adb:
    def __init__(self, exe, serial=None, timeout=120, log=print):
        self.exe, self.serial, self.timeout, self.log = str(exe), serial or None, timeout, log
        self.env = dict(os.environ, MSYS_NO_PATHCONV='1')   # Git Bash would rewrite /sdcard/... arguments into Windows paths

    def cmd(self, *a):
        return [self.exe] + (['-s', self.serial] if self.serial else []) + [str(x) for x in a]

    def run(self, *a, timeout=None, check=True, retries=3):
        err = ''
        for attempt in range(retries):
            try:
                r = subprocess.run(self.cmd(*a), capture_output=True, text=True, errors='replace', timeout=timeout or self.timeout, env=self.env)
                if r.returncode == 0 or not check: return r.stdout
                err = (r.stderr.strip() or r.stdout.strip())[-400:]   # adb's reason is on stderr; stdout has the files that went
                if a and a[0] == 'install': break   # an install failure is an answer, not a dropped link
            except subprocess.TimeoutExpired: err = f'timed out after {timeout or self.timeout} s'
            if attempt + 1 < retries:
                self.log(f'adb {a[0]} failed ({err}), retry {attempt + 1}')
                subprocess.run(self.cmd('wait-for-device'), timeout=300, env=self.env); time.sleep(2)
        raise AdbError(f'adb {a[0]}: {err}')

    def shell(self, script, **kw): return self.run('shell', script, **kw)

    # ---- devices ----
    def devices(self):
        """[(serial, state, description)] of every device adb sees"""
        out = subprocess.run([self.exe, 'devices', '-l'], capture_output=True, text=True, errors='replace', timeout=30, env=self.env).stdout
        rows = []
        for ln in out.splitlines()[1:]:
            parts = ln.split()
            if len(parts) >= 2: rows.append((parts[0], parts[1], ' '.join(p for p in parts[2:] if p.startswith(('model:', 'device:')))))
        return rows

    def pick(self):   # the configured device, else the only one connected
        ready = [s for s, st, _ in self.devices() if st == 'device']
        if self.serial:
            if self.serial not in ready: raise AdbError(f'device {self.serial} is not connected (connected: {", ".join(ready) or "none"})')
            return self.serial
        if len(ready) != 1: raise AdbError('no device connected' if not ready else f'several devices connected ({", ".join(ready)}): choose one')
        self.serial = ready[0]
        return self.serial

    def prop(self, name): return self.shell(f'getprop {shlex.quote(name)}').strip()

    def gpu(self):   # the GPU's name as SurfaceFlinger reports it ("Qualcomm, Adreno (TM) 830, OpenGL ES 3.2 ..."), '' when unknown
        out = self.shell('dumpsys SurfaceFlinger 2>/dev/null | grep -m1 "^GLES:" ; true', check=False).strip()
        return out[len('GLES:'):].strip() if out.startswith('GLES:') else ''

    def bc_textures(self):
        """Whether the GPU samples BC-compressed textures (the Switch's format, profile key requires bcn): Adreno and Xclipse do, Mali and PowerVR do not; None when unknown"""
        g = self.gpu().lower()
        if any(v in g for v in ('adreno', 'xclipse', 'nvidia')): return True
        if any(v in g for v in ('mali', 'powervr', 'immortalis')): return False
        return None

    def free_bytes(self, path='/sdcard'):
        out = self.shell(f'df -k {shlex.quote(path)} | tail -1', check=False).split()
        return int(out[3]) * 1024 if len(out) >= 4 and out[3].isdigit() else None

    def installed(self, package):
        return f'package:{package}' in self.shell(f'pm list packages {shlex.quote(package)}', check=False).split()

    # ---- install ----
    def install(self, apk, package, replace_signer=False):
        """adb install -r. A package installed with another signing key cannot be updated: replace_signer uninstalls it first (its saves in internal storage go with it)"""
        try: self.run('install', '-r', apk, timeout=600, retries=1)
        except AdbError as e:
            if 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' not in str(e): raise
            if not replace_signer:
                raise AdbError(f'{package} is installed with another signing key (another build of the game, a development build): '
                               'uninstall it on the device, or install with --replace-signer (its saves are deleted with it)') from e
            self.log(f'{package} has another signing key: uninstalling it first')
            self.run('uninstall', package, timeout=300, retries=1)
            self.run('install', apk, timeout=600, retries=1)

    def prepare_app_files(self, package, timeout=30):
        """Have Android create the app's files folder (/sdcard/Android/data/<package>/files) before anything is pushed into it: the system makes it, owned by the app with
        the app's group, when the app first asks for it. A folder the shell makes first lacks that group underneath FUSE, and the app cannot read what is pushed below it
        (NEO's port died at its first open, mods/main.fixups.tsv). So the app is started once (it stops at once without its data) and stopped again"""
        files = f'/sdcard/Android/data/{package}/files'
        if self.shell(f'[ -d {shlex.quote(files)} ] && echo yes; true').strip() == 'yes': return False
        self.shell(f'am start -W -n {package}/android.app.NativeActivity >/dev/null 2>&1; true', timeout=60)
        for _ in range(timeout * 2):
            if self.shell(f'[ -d {shlex.quote(files)} ] && echo yes; true').strip() == 'yes': break
            time.sleep(0.5)
        else: raise AdbError(f'{package} did not create its files folder ({files}) within {timeout} s of starting')
        self.shell(f'am force-stop {package}')
        return True

    def remote_sizes(self, rdir):   # {relative path: size} of every file under rdir on the device
        q = shlex.quote(rdir)
        out = self.shell(f'[ -d {q} ] && cd {q} && find . -type f -exec stat -c "%s %n" {{}} + ; true')
        have = {}
        for ln in out.splitlines():
            sz, _, name = ln.partition(' ')
            if sz.isdigit(): have[name[2:] if name.startswith('./') else name] = int(sz)
        return have

    def push_tree(self, local, remote, chunk=64 << 20, skip=(), keep=(), progress=None):
        """local folder → remote folder. skip: relative paths not pushed; keep: relative paths pushed only when the device has none (the player's settings).
        progress(done_bytes, total_bytes, note) after each transfer. Returns the bytes pushed"""
        local, remote = Path(local), remote.rstrip('/')
        files = sorted((p.relative_to(local).as_posix(), p) for p in local.rglob('*') if p.is_file())
        have = self.remote_sizes(remote)
        todo = [(rel, p, p.stat().st_size) for rel, p in files
                if rel not in skip and not rel.startswith('.dmpart') and (rel not in have if rel in keep else have.get(rel) != p.stat().st_size)]
        total, done = sum(s for _, _, s in todo), 0
        self.log(f'{len(todo):,} files to push, {total / 2**20:,.0f} MB ({len(files) - len(todo):,} already on the device)')
        for d in sorted({os.path.dirname(r) for r, _, _ in todo}): self.shell(f'mkdir -p {shlex.quote(f"{remote}/{d}" if d else remote)}')
        small = [(r, p, s) for r, p, s in todo if s <= chunk]
        for i in range(0, len(small), 32):   # small files: up to 32 per push, one push per directory
            part, by = small[i:i + 32], {}
            for r, p, s in part: by.setdefault(os.path.dirname(r), []).append(p)
            for d, ps in by.items():
                with short_paths(ps) as qs:
                    self.run('push', '-Z', *qs, f'{remote}/{d}/' if d else f'{remote}/', timeout=max(self.timeout, 600))
            done += sum(s for _, _, s in part)
            if progress: progress(done, total, f'{len(part)} files')
        for rel, p, size in [(r, p, s) for r, p, s in todo if s > chunk]:
            base = done
            self.push_file(p, f'{remote}/{rel}', chunk, progress=progress and (lambda d, t, note: progress(base + d, total, note)))
            done += size
        return total

    def push_file(self, local, dst, chunk=64 << 20, progress=None):
        """One file in pieces of chunk bytes, joined on the device; pieces already there are kept, so an interrupted push resumes. progress(done, size, note)"""
        local = Path(local); size = local.stat().st_size; n = max(1, (size + chunk - 1) // chunk)
        pdir = f'{os.path.dirname(dst)}/.dmpart-{hashlib.sha1(dst.encode()).hexdigest()[:12]}'   # one piece folder per file: a resumed push finds its own pieces
        self.shell(f'mkdir -p {shlex.quote(pdir)}'); pieces = self.remote_sizes(pdir)
        with tempfile.TemporaryDirectory(prefix='nx2a_push_') as t, open(local, 'rb') as f:
            for k in range(n):
                want, name = min(chunk, size - k * chunk), f'{k:05d}'
                if pieces.get(name) != want:
                    tmp = Path(t) / 'piece.bin'
                    f.seek(k * chunk); tmp.write_bytes(f.read(want))
                    self.run('push', '-Z', tmp, f'{pdir}/{name}', timeout=max(self.timeout, 600))
                if progress: progress(k * chunk + want, size, f'{local.name} piece {k + 1}/{n}')
        q, qp = shlex.quote(dst), shlex.quote(pdir)   # join the pieces in order, then check the size
        self.shell(f'rm -f {q} && for x in $(ls {qp} | sort); do cat {qp}/$x >> {q} || exit 1; done && rm -rf {qp}', timeout=1200)
        got = self.shell(f'stat -c %s {q}').strip()
        if got != str(size): raise AdbError(f'{local.name}: {got} bytes on the device, expected {size}')
