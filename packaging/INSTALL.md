# Installing nx2android

nx2android ports your own Nintendo Switch games to Android. This folder is the whole app: nothing to install with pip. It needs four things from you, once.

1. **Android NDK r27c**: download it from [developer.android.com/ndk/downloads](https://developer.android.com/ndk/downloads) and unzip it anywhere (only the NDK: no Android Studio, SDK or JDK).
2. **.NET SDK 10**: install it from [dotnet.microsoft.com/download](https://dotnet.microsoft.com/download).
3. **Android platform-tools** (adb), to install on your device from the app: [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools). Turn on USB debugging (or wireless debugging) on the device.
4. **Your own `prod.keys`**, dumped from your Switch. Keys and game files never leave your PC except into the app you build.

Then start **nx2android.exe**:

- **Setup** tab: every line should be green. Point it at the NDK folder, `dotnet.exe`, `adb.exe` or `prod.keys` if it did not find them.
- **Port** tab: choose the game's folder (the base game NSP or XCI, its update and DLC), click **Port**, then **Install** with the device connected.
- **Games** tab: the games with a profile and their status.

The first port of a game takes a while (extraction, rewriting the game's code, translating its shaders; the shader translator is built once, the first time). Later ports reuse what has not changed. The APK and the game's data appear in the game's folder.

The device's GPU must read BC-compressed textures (Adreno, Xclipse; not Mali or PowerVR). The command line is the same program: `nx2android.exe -m porter -h`.
