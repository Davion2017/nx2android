# Write NEO's provisional game profile into the nxnative clone (dm/games/010043B013C5C000) from the survey's extraction,
# with the same code the NSP script uses (write_profile + dm/games/profile_guess.py), without re-running the survey.
import sys, re
from pathlib import Path
repo = Path(sys.argv[1]); survey = Path(sys.argv[2])
sys.path[:0] = [str(repo / 'scripts'), str(repo / 'dm/games'), str(repo / 'dm/tools')]
import build_ipa_from_nsp as nsp, profile_guess as pg, nacp
ex = survey / 'extract'
F = pg.facts_of(ex / 'ExeFS', ex / 'romfs_manifest.tsv')
dv = re.search(r'display version (\S+)', (survey / 'logs/extract.log').read_text(errors='replace'))
facts = {'F': F, 'name': nacp.name(ex / 'control.nacp') or '', 'display': dv.group(1), 'version': 'v196608', 'survey': str(survey / 'survey.md')}
nsp.pg = pg; nsp.nacp = nacp
nsp.write_profile(repo / 'dm/games/010043B013C5C000', 0x010043B013C5C000, facts)
