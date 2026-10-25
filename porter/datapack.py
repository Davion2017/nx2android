# The data pack: everything the app reads from its files folder on the device (/sdcard/Android/data/<package>/files, front_android.c), as a folder beside the APK:
#   mods/          the rewritten code modules (patch_nso.py's outputs)
#   RomFS/         the game's files (the packed version's merged RomFS)
#   aoc/<index>/   the DLC the player has
#   shaders.dmsv   the Vulkan shaders (dm/android/tools/shader_vk.py)
#   env.txt        host switches: the game language, the DLC folder, the profile's env rows
#   settings.txt   the pause menu's first-launch defaults (the profile's setting rows); the installer never replaces the player's own
#   nx2a-data.json what the pack is (the installer checks it against the APK's package)
# Big trees are hard links into the extraction when the volume allows, so the pack takes no extra space; the pack is rebuilt whole when anything in it changes.
import json, os, shutil, time
from pathlib import Path

MANIFEST = 'nx2a-data.json'
KEEP_ON_DEVICE = ('settings.txt',)          # the player's choices win over the pack's defaults
OWNED = ('mods', 'RomFS', 'aoc')            # folders the pack owns on the device: files there that the pack lacks are stale (an older version's) and removed


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try: os.link(src, dst)
    except OSError: shutil.copy2(src, dst)


def link_tree(src, dst):   # (files, bytes)
    n = b = 0
    for root, _, files in os.walk(src):
        for f in files:
            s = Path(root) / f
            link_or_copy(s, dst / s.relative_to(src)); n += 1; b += s.stat().st_size
    return n, b


def files_folder(package): return f'/sdcard/Android/data/{package}/files'


def build(dst, *, profile, version, display, patched, romfs, shaders, aoc=None, language='en-US', package=None, progress=None):
    """Write the pack to dst (replacing it). profile: the AndroidProfile; package: the app's, when not the profile's. Returns the manifest"""
    package = package or profile.package
    tmp = dst.with_name(dst.name + '.partial')
    if tmp.exists(): shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    n = b = 0
    for what, src, sub in (('the rewritten modules', patched, 'mods'), ('the RomFS', romfs, 'RomFS'), ('the DLC', aoc, 'aoc')):
        if not src: continue
        if progress: progress(what)
        dn, db = link_tree(src, tmp / sub); n += dn; b += db
    link_or_copy(shaders, tmp / 'shaders.dmsv'); n += 1; b += shaders.stat().st_size
    env = [f'# Written by nx2android\'s porter for {profile.name} ({profile.id}); KEY=VALUE per line, read by the app at launch',
           f'DM_LANG={language}']
    if aoc: env.append(f'DM_AOC_DIR={files_folder(package)}/aoc')
    env += profile.env
    (tmp / 'env.txt').write_text('\n'.join(env) + '\n', encoding='utf-8', newline='\n')
    if profile.settings: (tmp / 'settings.txt').write_text(''.join(f'{k}={v}\n' for k, v in profile.settings.items()), encoding='utf-8', newline='\n')
    man = dict(title_id=profile.id, name=profile.name, package=package, version=version, display=display, language=language,
               files=n, bytes=b, dlc=sorted(int(p.name) for p in aoc.iterdir() if p.is_dir() and p.name.isdigit()) if aoc else [], made=time.strftime('%Y-%m-%d %H:%M:%S'))
    (tmp / MANIFEST).write_text(json.dumps(man, indent=2), encoding='utf-8')
    if dst.exists(): shutil.rmtree(dst)
    tmp.rename(dst)
    return man


def read_manifest(d):
    try: return json.loads((Path(d) / MANIFEST).read_text(encoding='utf-8'))
    except (OSError, ValueError): return None
