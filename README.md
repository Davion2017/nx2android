# nx2android

Port your own Nintendo Switch games to Android, natively: the game's own arm64 code runs on the device, with the Switch's system services stood in for by a host and NVN graphics replayed on Vulkan. Pick the game's folder, click **Port**, and get an APK plus the game's data, installed on your device if you like. Bring your own game files and keys; nothing from any game is in this repository.

This is the Android port of [nxnative](https://github.com/seedds/nxnative), which does the same on iPhone and iPad. How it is put together: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Games

| Game | Title ID | Status |
|---|---|---|
| Graveyard Keeper 2 | `0100005027A18000` | playable on the Legion Y700, update 1.0.4: the opening at a held 30 fps (as on the Switch) |
| NEO: The World Ends with You | `010043B013C5C000` | playable on a Lenovo Legion Y700 (Snapdragon 8 Elite, Adreno 830), update 1.03 |
| Viractal: Will You Trust Your Party? | `0100FD501F95A000` | playable on the Legion Y700 (board game turns, name entry), update 1.4.5 |
| Xenoblade Chronicles 3 | `010074F013262000` | playable on the Legion Y700, update 2.2.0 with its DLC: the opening, battles and the story to Torchlight Hill at 30 fps (heavy views of Torchlight Hill about 40 ms a frame). Known issue: the sky's cloud layer drops out for a few frames at a time, worst while the camera turns. Some shaders exist only at run time; the app captures them and the next port adds them |

Each game is a profile in `nxnative/dm/games/<title ID>/` with an `android.tsv`. The device's GPU must read BC-compressed textures (Adreno, Xclipse; not Mali or PowerVR).

## Setup

The app comes as a bundle: unzip `nx2android-<version>.zip` and start `nx2android.exe` ([packaging/INSTALL.md](packaging/INSTALL.md)). From the repository instead, install [Python](https://www.python.org) 3.11 or later and `python -m pip install -r requirements.txt`. Either way, install once:
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
