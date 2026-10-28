# Release check

Which games the player's bundle has been checked to port, from the game files to an APK and a data pack, on a Windows PC with nothing from the developer's machine: the bundle unzipped into an empty folder, its own player folder, the tools from its **Download missing tools**, and a game folder holding only the game's NSP files. Which games play is in [PORT_STATUS.md](PORT_STATUS.md).

A release ships when every row of the results below has been ported by the bundle it ships.

## When to run the check again

| What changed | Run the check for |
|---|---|
| A new game profile (`nxnative/dm/games/<title ID>/` only) | that game: add its row |
| A game's profile (its `android.tsv`, `game.tsv`, `patches.py`) | that game |
| The core (`porter/`, `packaging/`, `nxnative/dm/{host,gfx,tools,android,third_party}`, `nxnative/scripts/`), or the NDK or .NET version | every game |
| `gui/` or docs only | nothing (start the app once) |

## How

1. Build the bundle (`python packaging/build_bundle.py`) and unzip it into an empty folder, say `C:\nx2a-test\nx2android`.
2. Once per test folder, with a player folder of its own: `set NX2A_HOME=C:\nx2a-test\home`, then `nx2android.exe -m porter tools --download` and `nx2android.exe -m porter config keys <prod.keys>`.
3. Give each game a folder of hard links to its NSP files (`mklink /H <new> <nsp>`, or `ln` in Git Bash): a port from scratch without copying the game.
4. `python devtools/port_check.py C:\nx2a-test\nx2android <game folder> … --fresh --write` ports each one and puts its row below, replacing that game's earlier row.

## Results

The v0.1.0 check (2026-10-27): bundle `7d2b374` ported four games and stopped on NEO, whose committed shader tables lacked the 20 Unity compute shaders the split reads since `386efda`. Bundle `e89aecb` differs from it only in NEO's profile tables and ported NEO. v0.1.0 differs from `e89aecb` only in documents. The v0.1.0 NEO port, installed beside the player's own as `org.nx2a.neo.test`, then played on the Legion Y700: through the DLC gifts and the opening, into free roam at Scramble Crossing with its crowd, at 40-60 fps, with no new `[RED]` lines.

The v0.1.1 check (2026-10-27): bundle `bd68d8b` (v0.1.0-5-gbd68d8b) ported Hades II, the game it adds, from scratch. By the maintainer's choice only the new game was checked for this release: the Vulkan backend changes it brings (`c9c9e38`) were not run through the check for the other five games, whose rows are still from v0.1.0's bundles. v0.1.1 differs from `bd68d8b` only in documents. The release build installed on the Legion Y700 (`org.nx2a.hades2`) was ported from the development checkout at `75a1a18`, the same sources but for the version number, and starts at the title at 60 fps.

The Tales of Eternia Remastered check (2026-10-27): bundle `8372959` (v0.1.1-1-g8372959) ported it, the game it adds, from scratch. The same commit makes AAudio call back every 5 ms for every game (`audiotoolbox_aaudio.c`); the other games' rows are still from earlier bundles, and only Tales of Eternia was played with that change.

The v0.1.2 release (2026-10-28): by the maintainer's choice no bundle was run through the check. The maintainer instead rebuilt every game from the development checkout while testing on 2026-10-28, and these were played on the Legion Y700 that day: NEO, Hades II, Unpacking and Tales of Eternia from a fresh build folder at `21a0d68` (60 fps), Graveyard Keeper 2 at 60 fps (`21a0d68`), Mario vs. Donkey Kong (`d84dca1`). The core changes since v0.1.1 that touch every game were therefore not run through the check: the display-timed presents (`4802f3c`), the frame rate governor (`dba318d`), the node area cut on the sdk build Graveyard Keeper 2, Tales of Eternia and Viractal share (`8056043`), AAudio's 5 ms callbacks (`8372959`), the FPS counter (`27b96fc`), and the porter's Windows fixes (`e490097`, `2ee2723`). Mario vs. Donkey Kong has no row below: no bundle has ported it yet.

<!-- port_check rows -->
| Game | Title ID | Version | Result | Output | Time | Bundle | Date |
|---|---|---|---|---|---|---|---|
| Graveyard Keeper 2 | `0100005027A18000` | 1.0.4 | ported | APK 1 MB, data 1.4 GB, 1 DLC | 4 min (from scratch) | 7d2b374 | 2026-10-27 |
| Hades II | `0100A00019DE0000` | 1.0.141667 | ported | APK 2 MB, data 4.7 GB | 1 min (from scratch) | v0.1.0-5-gbd68d8b | 2026-10-27 |
| NEO: The World Ends with You | `010043B013C5C000` | 1.03 | ported | APK 2 MB, data 6.7 GB, 2 DLC | 3 min (from scratch) | e89aecb | 2026-10-27 |
| Tales of Eternia Remastered | `010006E0230AC000` | 2.0.0 | ported | APK 2 MB, data 5.6 GB | 4 min (from scratch) | v0.1.1-1-g8372959 | 2026-10-27 |
| Unpacking | `0100701015846000` | 2.01 | ported | APK 2 MB, data 1.0 GB | 2 min (from scratch) | 7d2b374 | 2026-10-27 |
| Viractal | `0100FD501F95A000` | 1.4.5 | ported | APK 2 MB, data 2.3 GB | 5 min (from scratch) | 7d2b374 | 2026-10-27 |
| Xenoblade Chronicles 3 | `010074F013262000` | 2.2.0 | ported | APK 2 MB, data 19.2 GB, 4 DLC | 4 min (from scratch) | 7d2b374 | 2026-10-27 |
<!-- /port_check rows -->
