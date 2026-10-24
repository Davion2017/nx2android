# nx2android

Porting Nintendo Switch games to Android, natively: the game's own arm64 code runs on the device, with the Switch's system services stood in for by a host and NVN graphics replayed on Vulkan. Bring your own game files and keys; nothing from any game is in this repository.

This is the Android port of [nxnative](https://github.com/seedds/nxnative), which does the same on iPhone and iPad.

## Layout

- `nxnative/`: nxnative, kept as a git subtree of `seedds/nxnative` (squashed) with the Android port on top. The Android host is in `nxnative/dm/android/` (Vulkan backend, front end with the on-screen gamepad and pause menu, `build.py`, `apk/mkapk.py`); game profiles are in `nxnative/dm/games/<title ID>/`.
- `probes/`: the first on-device probes (CPU, Vulkan, zero-copy memory pools).
- `scripts/`: development tools for a connected device (pushing files, screen recording, soak tests, pass traces).
- `RESEARCH.md`: the feasibility study and the device results.

Not committed (see `.gitignore`): `tools/` (Android NDK r27c, .NET SDK, platform-tools, Vulkan validation layer, the local APK signing key), `work/` and `build/`.

## Games

| Game | Title ID | Status |
|---|---|---|
| NEO: The World Ends with You | `010043B013C5C000` | Boots and plays on a Lenovo Legion Y700 (Snapdragon 8 Elite, Adreno 830) |

## Updating nxnative

```
git subtree pull --prefix nxnative https://github.com/seedds/nxnative.git main --squash
```

## License

MIT, as nxnative (see `nxnative/LICENSE`). Third-party code keeps its own license.
