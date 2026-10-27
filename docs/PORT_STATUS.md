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

<!-- port_check rows -->
<!-- /port_check rows -->
