# Minimalus Mobile

Minimalus Mobile is the Android companion build for **Minimalus UI v3.0**, gkoogz / Jujin's slim Guild Wars interface mod. It packages the Guild Wars Reforged mobile web client in an Android WebView and applies the Minimalus texture replacement table at runtime.

The public APK is intended for easy sideloading: download it from the latest GitHub release on an Android device, allow the browser to install unknown apps when Android prompts you, and launch **Minimalus Mobile**.

## Latest APK

Download the current APK from the [latest MinimalusMobile release](https://github.com/gkoogz/MinimalusMobile/releases/latest).

This first public build is a community beta. It has reached the live game world on the author's Android tablet with Minimalus injection active, but it has not yet had broad device, OS, reinstall, account, or game-update soak testing.

## What This Build Does

- Serves the bundled Guild Wars Reforged web client from a stable local origin.
- Proxies required patch and login traffic through the Android app so the WebView can complete the native mobile login flow.
- Patches the downloaded game client script before execution.
- Replaces matching runtime textures with Minimalus UI v3.0 textures.
- Gives mobile-specific texture edits priority over the PC texture set.

The replacement table is generated from the working Minimalus folders:

1. `Altered` and `Unaltered` provide the PC/desktop baseline.
2. `AlteredMobile` and `UnalteredMobile` are applied afterward and override matching entries.

The repo also includes a snapshot of those source texture folders under `assets/` so the shipped APK can be audited and rebuilt from the same DDS inputs.

## Build From Source

Requirements:

- JDK 17 or newer
- Android SDK with compile SDK 35
- Gradle or Android Studio
- Python 3.11+
- Microsoft DirectX SDK `texconv.exe` for regenerating texture replacements from DDS files

Build the checked-in Android project:

```powershell
cd C:\path\to\MinimalusMobile
gradle assembleDebug
```

The APK is written to:

```text
app\build\outputs\apk\debug\app-debug.apk
```

## Regenerate The Texture Table

By default the tool reads the author's local Minimalus pipeline folder when it exists:

```text
C:\Users\Administrator\Documents\Minimalus UI 3.0 Pipeline\working\Minimalus UI 3.0
```

To use another folder, set `MINIMALUS_PIPELINE_DIR` to a directory containing these four subfolders. A checked-in snapshot is available at `assets/`.

- `Altered`
- `Unaltered`
- `AlteredMobile`
- `UnalteredMobile`

Then run:

```powershell
$env:MINIMALUS_PIPELINE_DIR = "C:\path\to\Minimalus UI 3.0"
python tools\build_minimalus_mobile_app.py
gradle assembleDebug
```

The generated replacement manifest is also written under `outputs\`.

## Mobile Texture Probe

The probe is included for future maintenance when ArenaNet changes, renames, or resizes native mobile textures. It is a developer tool, not part of the normal player install flow.

Start the bridge on the PC:

```powershell
python tools\mobile_texture_bridge.py
```

Connect the Android device with USB debugging enabled, then route the app back to the PC:

```powershell
adb reverse tcp:8787 tcp:8787
```

Open the bridge UI on the PC:

```text
http://127.0.0.1:8787
```

The bridge can request capture, reset capture state, page through captured textures, preview the selected texture, and dump selected native mobile textures as DDS files into `UnalteredMobile` by default. Override the dump destination with:

```powershell
$env:MINIMALUS_UNALTERED_DIR = "C:\path\to\UnalteredMobile"
```

Probe caveats:

- It is intentionally experimental.
- Text rendering can produce noisy captures.
- Highlighting and capture state should be reset between runs.
- For ordinary users, use the release APK instead of the probe.

## Stability Status

This APK is installable and functional enough for a public beta, but it should not be described as fully stable yet. A final stable release should be verified against:

- clean install from browser download
- app restart after successful login
- device reboot
- game client update / patch refresh
- at least two Android devices or OS versions
- texture replacement count in logcat
- in-game visual pass through inventory, skills, party, map, chat, and login UI

## Related Projects

- [MinimalusUIMod](https://github.com/gkoogz/MinimalusUIMod)
- [uMod Reforged](https://github.com/gkoogz/uMod-Reforged)
