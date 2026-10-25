# The command line (python -m porter …). Every command the GUI uses is here, so a port runs the same headless. Exit codes: 0 done, 1 error, 130 interrupted.
import argparse, json, os, sys
from pathlib import Path


def _parser():
    ap = argparse.ArgumentParser(prog='porter', description='Port your own Switch game files to an Android app (docs/ARCHITECTURE.md).')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('doctor', help='check the tools a port needs'); d.add_argument('--json', action='store_true'); d.add_argument('-k', '--keys')
    p = sub.add_parser('profiles', help='list the games the tool can port'); p.add_argument('--all', action='store_true', help='also the iOS profiles not ported to Android'); p.add_argument('--json', action='store_true')
    i = sub.add_parser('inspect', help='what a game folder holds and whether it can be ported'); i.add_argument('folder'); i.add_argument('--json', action='store_true')
    po = sub.add_parser('port', help='make the APK and the data pack (and install them)')
    po.add_argument('folder', help='the game\'s folder: its base game NSP / XCI, updates and DLC')
    po.add_argument('-k', '--keys', help='prod.keys (default: the configured one)')
    po.add_argument('-o', '--out', help='folder for the APK and the data pack (default: the game folder)')
    po.add_argument('-p', '--version', default='', help='version to pack, v<N> (default: the newest in the folder)')
    po.add_argument('-l', '--language', default='', help='game language, a code or a name (default: English)')
    po.add_argument('--app-name', default='', help='the app\'s name on the device (default: the game\'s name)')
    po.add_argument('--install', action='store_true', help='install on the connected device afterwards')
    po.add_argument('--device', default='', help='adb serial of the device to install on')
    po.add_argument('--replace-signer', action='store_true', help='uninstall an app of the same package signed with another key first (deletes its saves)')
    po.add_argument('--debug', action='store_true', help='a development build: debug information, debuggable, DM_CTL key presses')
    po.add_argument('--jobs', type=int, default=os.cpu_count() or 8)
    po.add_argument('--progress', default='auto', choices=('auto', 'bar', 'lines', 'json', 'off'), help='json: one JSON event per line, for the GUI')
    ins = sub.add_parser('install', help='install a port made earlier'); ins.add_argument('data', help='the data pack folder (<App>-data)'); ins.add_argument('--apk', help='the APK (default: <App>.apk beside the pack)')
    ins.add_argument('--device', default=''); ins.add_argument('--replace-signer', action='store_true'); ins.add_argument('--progress', default='auto', choices=('auto', 'bar', 'lines', 'json', 'off'))
    dv = sub.add_parser('devices', help='the devices adb sees'); dv.add_argument('--json', action='store_true')
    c = sub.add_parser('config', help='show or change the saved settings'); c.add_argument('key', nargs='?'); c.add_argument('value', nargs='?')
    return ap


def _print_json(obj): print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_doctor(a):
    from porter import toolchain
    rows = toolchain.checks(keys=a.keys)
    if a.json: _print_json([r.as_dict() for r in rows])
    else:
        for r in rows: print(f'{"ok " if r.ok else ("!! " if r.required else "-- ")} {r.name:15} {r.detail}' + (f'\n{"":19}→ {r.fix}' if r.fix and not r.ok else ''))
    return 0 if all(r.ok or not r.required for r in rows) else 1


def cmd_profiles(a):
    from porter import profiles
    rows = profiles.all_entries(android_only=not a.all)
    if a.json: _print_json([r.as_dict() for r in rows]); return 0
    for r in rows: print(f'{r.id}  {r.status:12} {r.name}' + (f'  ({r.tested})' if r.tested else ''))
    return 0


def cmd_inspect(a):
    from porter import pipeline
    info = pipeline.inspect(a.folder)
    if a.json: _print_json(info); return 0 if info['supported'] else 2
    print(f'{info["title_id"]}  {info.get("name", "")}\n  base: {info["base"]}')
    for u in info['updates']: print(f'  update {u["version"]}: {u["file"]}')
    for d in info['dlc']: print(f'  DLC {d["title_id"]}: {d["file"]}')
    if info.get('pack'): print(f'  packs {info["pack"]} (versions in the folder: {", ".join(info["versions"])})')
    if info['android']: print(f'  Android: {info["android"]["status"]}' + (f', tested on {info["android"]["tested"]}' if info['android']['tested'] else ''))
    if info['reason']: print(f'  {info["reason"]}')
    return 0 if info['supported'] else 2


def _with_progress(mode, fn):
    from porter.upstream import BuildError, PROG, nsp
    PROG.mode = nsp.progress_mode(mode)
    environ = dict(os.environ)
    try:
        fn(); return 0
    except BuildError as e:
        PROG.close(ok=False); PROG.say(f'[RED] {e}'); return 1
    except KeyboardInterrupt:
        PROG.close(ok=False); PROG.say('[RED] interrupted'); return 130
    except Exception as e:
        PROG.close(ok=False)
        if PROG.mode == 'json': PROG.say(f'[RED] {type(e).__name__}: {e}')
        raise
    finally:
        PROG.close(ok=False)
        for k in os.environ.keys() - environ.keys(): del os.environ[k]
        os.environ.update(environ)


def cmd_port(a):
    from porter import pipeline
    opts = pipeline.Options(folder=Path(a.folder), keys=Path(a.keys) if a.keys else None, out=Path(a.out) if a.out else None, version=a.version, language=a.language,
                            app_name=a.app_name, install=a.install, device=a.device, replace_signer=a.replace_signer, debug=a.debug, jobs=a.jobs)
    return _with_progress(a.progress, lambda: pipeline.emit_result(pipeline.Port(opts).run()))


def cmd_install(a):
    from porter import config, datapack, install, toolchain
    from porter.upstream import BuildError, PROG
    def go():
        data = Path(a.data).resolve()
        apk = Path(a.apk) if a.apk else data.with_name(data.name.removesuffix('-data') + '.apk')
        PROG.plan(1)
        cfg = config.load()
        install.install(apk, data, toolchain.find_adb(cfg), a.device or cfg.get('device'), replace_signer=a.replace_signer)
    return _with_progress(a.progress, go)


def cmd_devices(a):
    from porter import config, toolchain
    from porter.adb import Adb
    exe = toolchain.find_adb()
    if not exe: print('adb not found', file=sys.stderr); return 1
    rows = Adb(exe).devices()
    if a.json: _print_json([{'serial': s, 'state': st, 'info': d} for s, st, d in rows]); return 0
    for s, st, d in rows: print(f'{s}\t{st}\t{d}')
    if not rows: print('no device')
    return 0


def cmd_config(a):
    from porter import config
    if a.key is None:
        for k, v in config.load().items(): print(f'{k:9} {v or "-":40}  {config.KEYS[k]}')
        print(f'({config.path()})'); return 0
    if a.value is None: print(config.load().get(a.key, '')); return 0
    try: config.set_value(a.key, a.value)
    except KeyError as e: print(e.args[0], file=sys.stderr); return 1
    return 0


def main(argv):
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # game names and progress bars on a Windows console
    a = _parser().parse_args(argv)
    return {'doctor': cmd_doctor, 'profiles': cmd_profiles, 'inspect': cmd_inspect, 'port': cmd_port, 'install': cmd_install, 'devices': cmd_devices, 'config': cmd_config}[a.cmd](a)
