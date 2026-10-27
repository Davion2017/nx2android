# Port status

Which games the player's bundle has been checked to port, from the game files to an APK and a data pack, on a Windows PC with nothing from the developer's machine: the bundle unzipped into an empty folder, its own player folder, the tools from its **Download missing tools**, and a game folder holding only the game's NSP files. Whether a game then plays, and on which device, is the profile's `status` and `tested` (the README's games table).

A release ships when every row here has been ported by the bundle it ships.

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

The v0.1.0 check (2026-10-27): bundle `7d2b374` ported four games and stopped on NEO, whose committed shader tables lacked the 20 Unity compute shaders the split reads since `386efda`. Bundle `e89aecb` differs from it only in NEO's profile tables and ported NEO. v0.1.0 differs from `e89aecb` only in documents. NEO's added shaders have not yet been played on a device.

<!-- port_check rows -->
| Game | Title ID | Version | Result | Output | Time | Bundle | Date |
|---|---|---|---|---|---|---|---|
| Graveyard Keeper 2 | `0100005027A18000` | 1.0.4 | ported | APK 1 MB, data 1.4 GB, 1 DLC | 4 min (from scratch) | 7d2b374 | 2026-10-27 |
| NEO: The World Ends with You | `010043B013C5C000` | 1.03 | ported | APK 2 MB, data 6.7 GB, 2 DLC | 3 min (from scratch) | e89aecb | 2026-10-27 |
| Unpacking | `0100701015846000` | 2.01 | ported | APK 2 MB, data 1.0 GB | 2 min (from scratch) | 7d2b374 | 2026-10-27 |
| Viractal | `0100FD501F95A000` | 1.4.5 | ported | APK 2 MB, data 2.3 GB | 5 min (from scratch) | 7d2b374 | 2026-10-27 |
| Xenoblade Chronicles 3 | `010074F013262000` | 2.2.0 | ported | APK 2 MB, data 19.2 GB, 4 DLC | 4 min (from scratch) | 7d2b374 | 2026-10-27 |
<!-- /port_check rows -->
