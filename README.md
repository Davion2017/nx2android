# nx2android

Port your own Nintendo Switch games to Android, natively: the game's own arm64 code runs on the device, with the Switch's system services stood in for by a host and NVN graphics replayed on Vulkan. Pick the game's folder, click **Port**, and get an APK plus the game's data, installed on your device if you like. Bring your own game files and keys; nothing from any game is in this repository.

This is the Android port of [nxnative](https://github.com/seedds/nxnative), which does the same on iPhone and iPad. How it is put together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Games

| Game | Title ID | Status |
|---|---|---|
| Graveyard Keeper 2 | `0100005027A18000` | playable on the Legion Y700, update 1.0.4: the opening at a held 30 fps (as on the Switch) |
| Hades II | `0100A00019DE0000` | playable on the Legion Y700, update 1.0 (v655360): the title, a new save, the Crossroads and runs in Erebus with combat, at a held 60 fps (as on the Switch) |
| NEO: The World Ends with You | `010043B013C5C000` | playable on a Lenovo Legion Y700 (Snapdragon 8 Elite, Adreno 830), update 1.03 |
| Unpacking | `0100701015846000` | playable on the Legion Y700, update 2.01: by touch, docked and handheld, at a held 60 fps (as on the Switch) |
| Viractal: Will You Trust Your Party? | `0100FD501F95A000` | playable on the Legion Y700 (board game turns, name entry), update 1.4.5 |
| Xenoblade Chronicles 3 | `010074F013262000` | playable on the Legion Y700, update 2.2.0 with its DLC: the opening, battles and the story to Torchlight Hill. Holds 30 fps in Performance and Resolution mode, in the field and in battle (frame p95 under 35 ms on Everblight Plain; heavy views of Torchlight Hill took about 40 ms a frame before these fixes and are not re-measured). Some shaders exist only at run time; the app captures them and the next port adds them |

Each game is a profile in `nxnative/dm/games/<title ID>/` with an `android.tsv`. The device's GPU must read BC-compressed textures (Adreno, Xclipse; not Mali or PowerVR).

## For players: port a game without programming

1. Download `nx2android-<version>-windows-x64.zip` from [Releases](https://github.com/shirai91/nx2android/releases/latest), unzip it and start **nx2android.exe**.
2. **Setup** tab: click **Download missing tools** (the Android NDK, the .NET SDK and platform-tools, about 1 GB, from Google and Microsoft), then set your **prod.keys**. Every line turns green.
3. **Port** tab: choose the folder with the game's NSP or XCI files (base game, update, DLC) and click **Port**.
4. Tick **Install on the device when done** with the device plugged in and USB debugging on, or copy the APK and the data folder yourself.

The step-by-step guide is [packaging/INSTALL.md](packaging/INSTALL.md). Which games each release has been checked to port: [docs/PORT_STATUS.md](docs/PORT_STATUS.md). You need your own game files and `prod.keys`, dumped from your own Switch; the tool never ships or downloads either. NSZ files must be decompressed to NSP first.

## Setup from the repository

Install [Python](https://www.python.org) 3.11 or later and `python -m pip install -r requirements.txt`, then `python -m porter tools --download` (or install them yourself):
- [Android NDK r27c](https://developer.android.com/ndk/downloads) (only the NDK: no Android Studio, SDK or JDK)
- [.NET SDK 10](https://dotnet.microsoft.com/download)
- Android [platform-tools](https://developer.android.com/tools/releases/platform-tools) (adb), to install from the tool
- your own `prod.keys`, dumped from your Switch

## Port a game

The app:

```
python -m gui
```

Check the **Setup** tab, choose the game's folder (the base game NSP or XCI, its update and DLC) on the **Port** tab, and click **Port**.

Or the command line:

```
python -m porter doctor
python -m porter port "D:\Games\NEO" -k "D:\keys\prod.keys" --install
```

The APK (`NeoTheWorldEndsWithYou.apk`) and the data pack (`NeoTheWorldEndsWithYou-data/`) appear in the game folder (`-o` picks another). The first port takes a while (extraction, rewriting the game's code, translating its shaders); later ones reuse what has not changed. `python -m porter -h` lists the commands.

## Layout

- `porter/`: the port pipeline (`python -m porter`).
- `gui/`: the desktop app (`python -m gui`).
- `nxnative/`: nxnative, kept as a git subtree of `seedds/nxnative` (squashed), with the Android runtime in `nxnative/dm/android/` and the game profiles in `nxnative/dm/games/`.
- `packaging/`: the player's bundle (`python packaging/build_bundle.py`).
- `devtools/`: scripts for bringing up a game on a connected device (`devtools/device.json` names the device: `{"serial": "...", "package": "..."}`).
- `probes/`, `RESEARCH.md`: the feasibility study and the first on-device probes.

## Building the bundle

```
python -m pip install -r requirements.txt pyinstaller
python packaging/build_bundle.py
```

`dist/nx2android/` and `dist/nx2android-<version>.zip`: the app, the committed `nxnative/` and the install guide; no toolchains, keys or game files.

## Tests

```
python -m unittest discover tests
```

## Updating nxnative

```
git subtree pull --prefix nxnative https://github.com/seedds/nxnative.git main --squash
```

## License

MIT, as nxnative (see `nxnative/LICENSE`). Third-party code keeps its own license.
