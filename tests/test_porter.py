# Unit tests of the port pipeline's own parts (python -m unittest discover tests). They need no game files, toolchains or device.
import json, os, re, shutil, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.environ['NX2A_HOME'] = tempfile.mkdtemp(prefix='nx2a_test_home_')

from porter import config, datapack, pipeline, profiles   # noqa: E402
from porter.upstream import android_profile, game          # noqa: E402

NEO = '010043B013C5C000'


def profile_dir(rows, gid='0100000000AAA000'):
    """A throwaway game profile with an android.tsv of these rows, found through DM_GAMES_DIR"""
    root = Path(tempfile.mkdtemp(prefix='nx2a_test_profiles_')); d = root / gid; d.mkdir()
    (d / 'game.tsv').write_text(f'title_id\t{gid}\nprogram_id\t{gid}\nname\tTest Game\nipa\tTestGame.ipa\nmodules\tmain sdk\n', encoding='utf-8')
    (d / 'android.tsv').write_text(''.join(f'{k}\t{v}\n' for k, v in rows), encoding='utf-8')
    os.environ['DM_GAMES_DIR'] = str(root)
    return d


class AndroidProfiles(unittest.TestCase):
    def tearDown(self): os.environ.pop('DM_GAMES_DIR', None)

    def test_neo(self):
        p = profiles.load(NEO)
        self.assertEqual(p.status, 'playable'); self.assertEqual(p.package, 'org.nx2a.neo'); self.assertTrue(p.landscape)
        self.assertEqual(p.settings, {'docked': '0', 'overlay': '1', 'rumble': '1'}); self.assertEqual(p.requires, ['bcn'])

    def test_only_android_profiles_listed(self):
        rows = profiles.all_entries()
        self.assertIn(NEO, [r.id for r in rows]); self.assertTrue(all(r.android for r in rows))
        self.assertGreater(len(profiles.all_entries(android_only=False)), len(rows))

    def test_default_package(self):
        d = profile_dir([('status', 'boots')])
        self.assertEqual(android_profile.load(d.name).package, 'org.nx2a.t0100000000aaa000')

    def test_bad_keys_are_refused(self):
        for rows in ([('status', 'great')], [('colour', 'red')], [('setting', 'volume=3')], [('overlay', 'q 0.1 0.2')], [('env', 'lower=1')], [('package', 'Not A Package')],
                     [('status', 'boots'), ('status', 'playable')]):
            d = profile_dir(rows)
            with self.assertRaises(android_profile.ProfileError, msg=rows): android_profile.load(d.name)

    def test_header_default_layout(self):   # the generated table is overlay_layout.h's table as it was written by hand before it moved to overlay_default.tsv
        h = android_profile.header(android_profile.load(NEO))
        rows = re.findall(r'\{(OV_\w+), ([\d.]+)f, ([\d.]+)f, ([\d.]+)f, (\w+), "([^"]*)"\}', h)
        self.assertEqual(len(rows), 16)
        self.assertEqual(rows[0], ('OV_STICK_L', '0.12', '0.70', '0.12', '0', ''))
        self.assertEqual(rows[2], ('OV_BUTTON', '0.935', '0.60', '0.050', 'DM_BTN_A', 'A'))
        self.assertEqual(rows[10][-1], '-')   # the minus button's label, not "no label"

    def test_header_overlay_move(self):
        d = profile_dir([('status', 'boots'), ('overlay', 'a 0.5 0.5 0.07')])
        h = android_profile.header(android_profile.load(d.name))
        self.assertIn('{OV_BUTTON, 0.5f, 0.5f, 0.07f, DM_BTN_A, "A"}', h)


class DataPack(unittest.TestCase):
    def test_build(self):
        t = Path(tempfile.mkdtemp(prefix='nx2a_test_pack_'))
        try:
            (t / 'patched').mkdir(); (t / 'patched/main.patched.bin').write_bytes(b'x' * 10)
            (t / 'romfs/Data').mkdir(parents=True); (t / 'romfs/Data/a.bin').write_bytes(b'y' * 20)
            (t / 'aoc/1').mkdir(parents=True); (t / 'aoc/1/d.bin').write_bytes(b'z')
            (t / 'shaders.dmsv').write_bytes(b'DMSV')
            p = profiles.load(NEO)
            man = datapack.build(t / 'out-data', profile=p, version='v196608', display='1.03', patched=t / 'patched', romfs=t / 'romfs', shaders=t / 'shaders.dmsv',
                                 aoc=t / 'aoc', language='ja')
            o = t / 'out-data'
            self.assertTrue((o / 'mods/main.patched.bin').is_file()); self.assertTrue((o / 'RomFS/Data/a.bin').is_file()); self.assertTrue((o / 'aoc/1/d.bin').is_file())
            env = (o / 'env.txt').read_text()
            self.assertIn('DM_LANG=ja', env); self.assertIn('DM_AOC_DIR=/sdcard/Android/data/org.nx2a.neo/files/aoc', env)
            self.assertEqual((o / 'settings.txt').read_text(), 'docked=0\noverlay=1\nrumble=1\n')
            self.assertEqual((man['files'], man['bytes'], man['dlc'], man['requires']), (4, 35, [1], ['bcn']))   # the installer checks requires
            self.assertEqual(datapack.read_manifest(o)['package'], 'org.nx2a.neo')
        finally:
            shutil.rmtree(t, ignore_errors=True)


class Experimental(unittest.TestCase):
    def test_ios_profile_copied_with_experimental_android_tsv(self):   # an iOS-only profile is copied out of the repository, never edited in place
        odyssey = '0100000000010000'
        t = Path(tempfile.mkdtemp(prefix='nx2a_test_exp_')); environ = dict(os.environ)
        try:
            port = pipeline.Port(pipeline.Options(folder=t, experimental=True)); port.env = {}; port.work = t / f'{odyssey}_build'; port.o.keys = None
            g, ap = port.experimental_profile(game.load(odyssey), odyssey)
            self.assertEqual(g.dir, (t / f'{odyssey}_build/profile/{odyssey}').resolve())
            self.assertEqual((ap.status, ap.package), ('experimental', f'org.nx2a.t{odyssey}'))
            self.assertFalse((REPO / f'nxnative/dm/games/{odyssey}/android.tsv').exists())
            self.assertFalse((g.dir / 'patches.py').exists())   # patch_nso.py finds the per-build cuts in dm/games
            self.assertEqual(os.environ.get('DM_GAMES_FIRST'), '1')
        finally:
            os.environ.clear(); os.environ.update(environ); shutil.rmtree(t, ignore_errors=True)


class Misc(unittest.TestCase):
    def test_config_roundtrip(self):
        config.set_value('device', 'abc:5555'); self.assertEqual(config.load()['device'], 'abc:5555')
        with self.assertRaises(KeyError): config.set_value('nope', 'x')

    def test_version_code_grows_with_updates(self):
        self.assertLess(pipeline.version_code('v0'), pipeline.version_code('v65536'))
        self.assertEqual(pipeline.version_code('v196608'), 196609)

    def test_app_stem(self):
        self.assertEqual(pipeline.app_stem(game.load(NEO), 'NEO'), 'NeoTheWorldEndsWithYou')


if __name__ == '__main__':
    unittest.main()
