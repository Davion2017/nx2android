# Notes for agents

nx2android runs a player's own Switch game files as an Android app: the game's arm64 code runs natively, a host stands in for Horizon, NVN is replayed on Vulkan. `porter/` turns game files into an APK + data pack, `gui/` draws `porter`, `nxnative/` is a squashed git subtree of `seedds/nxnative` plus the Android port. Load the `nx2android-dev` skill for profile-or-core decisions and `switch-android-port` for device debugging; both are in `.claude/skills/`.

## Where a change goes

`tests/arch_rules.py` enforces this on the committed tree; read `docs/ARCHITECTURE.md` before changing a layer and keep it true.

- `nxnative/dm/android/` (Android runtime): **no** title IDs, game names or per-game packages in code. A game needing different behaviour gets an `android.tsv` key.
- `nxnative/dm/{host,gfx,tools,third_party}` (core shared with iOS): keep the diff small (it is merged by `git subtree pull`), platform differences behind `DM_ANDROID` / `__APPLE__` / `DM_TARGET`.
- `nxnative/dm/games/<title ID>/`: data only (`game.tsv`, `android.tsv`, shader tables), plus `patches.py` for per-build rewrites.
- `porter/`: no UI imports, nothing from `devtools/`; every GUI action must be a CLI subcommand (`gui/runner.py` only shells out to `python -m porter`).
- Prefer a general rule (Horizon / NVN / Vulkan semantics, what the binary or its files show) over a per-game branch or profile key.

## Commands

```
python -m pip install -r requirements.txt     # Python 3.11+; PySide6 needed for `gui`, pyyaml for tests
python -m unittest discover tests             # also `python tests/arch_rules.py` for the layer rules alone
python -m porter doctor | profiles | inspect <folder> | port <folder> -k <prod.keys> [--debug --install --package …]
python -m gui                                 # desktop app (PySide6)
```

- A port that has already run is incremental: expensive stages reuse their output from `<game folder>/<title ID>_build/`, the host build is incremental. Editing a profile's `android.tsv` does not rebuild shaders.
- `--debug` is required for `DM_CTL` key presses; a release build ignores `ctl.txt`.
- No engine tool has a default game: `DM_GAME=<id>` (shader tools) / `GAME=<id>` (`make -C dm/host`, `build_ipa.sh`). `porter` picks the profile itself.
- Build the player bundle with `python packaging/build_bundle.py` (after `python packaging/build_bootloader.py`).

## Hard rules

- Keys, NSP/XCI files and anything extracted from them never enter the repository, a commit or the chat: print key names, never values. Game folders live outside the repo; the port writes its build folder beside them.
- Commit only when asked, and only as `git -c user.name=seedds -c user.email=seedds@gmail.com commit`. Messages are Conventional Commits checked by `.githooks/commit-msg` (opt in once per clone with `git config core.hooksPath .githooks`); up to 100-char lines, the description may start with a capital.
- Ask before installing anything on the user's device: name the package and size, use `--package org.nx2a.<name>.test` for test builds, and uninstall them afterwards.
- Everything written is English (docs, comments, log lines); log lines for something unimplemented or wrong start with `[RED] `.
- Update `docs/PORT_STATUS.md` when a game's status changes (it is the only place the status table exists), and the profile's `android.tsv` `status` / `tested` to match. `playable` and `wip` require a `tested` row.
- A fix starts from evidence; put the observation in the comment beside it, as existing code does.

## Device and environment notes

- `devtools/` scripts and the device skills take the device and app from `devtools/device.json` (not committed) or `NX2A_DEVICE` / `NX2A_PACKAGE` / `NX2A_GAME`. Never hard-code a device or package there.
- In Git Bash, `export MSYS_NO_PATHCONV=1` before adb with `/sdcard/...` paths.
- The engine's tools write files with no explicit encoding: run them with `PYTHONUTF8=1` (porter sets it) or they break on Windows' code page.
- Large pushes must go through `devtools/push_chunked.py` or the installer (adb compression off); a plain adb push of a RomFS wedges adbd.
- Shader translation chain: after changing any `dmsh_*` tool, run `dmsh_chain.py --header` and commit `nxnative/dm/gfx/nvn/dmsh_chain.h` with it, then rebuild the affected profile's shaders and the host. `nxnative/dm/gfx/tools/dmsh_xlate_bin` matches `dmsh_chain.lock`; a fresh `dotnet publish` does not.

## Further reading

- `docs/ARCHITECTURE.md` — layers, `android.tsv` keys, the port's stages, events protocol.
- `nxnative/AGENTS.md` and `nxnative/dm/games/README.md` — upstream engine rules and every `game.tsv` key.
- `nxnative/docs/agents/` — upstream bring-up guide (extract, survey, failure catalogue, graphics, debugging).
- `.claude/skills/nx2android-dev/references/` — profile vs core, device loop, builds on the device.
