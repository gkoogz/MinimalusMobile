# Steam login maintenance

Minimalus Mobile 1.0.5 shipped before ArenaNet enabled mobile Steam login on July 21, 2026. Its bundled loader had no Steam provider. Updating downloaded game data did not update that bundled loader or add an Android OAuth bridge.

The 1.0.6 source imports the retail Android **1.1.7 / build 38735** loader. The retail package declares Steam OAuth client ID `CE9BDCEC`, authorization URL `https://steamcommunity.com/oauth/login`, redirect `https://www.guildwars.com/app/live/auth`, and implicit token response. Its login implementation passes the Steam access token to the game as `{ refreshToken: token }` and caches it for one year. The public identifier and redirect are copied from that package; no Steam client secret is used.

## Source and import

ArenaNet confirms mobile Steam login in its [mobile FAQ](https://help.guildwars.com/hc/en-us/articles/51186731021587-Guild-Wars-Reforged-Mobile-FAQ). The app is listed on [Google Play](https://play.google.com/store/apps/details?id=net.arena.guildwars.reforged). The 1.1.7 package used for this update was obtained from [APKPure](https://apkpure.net/guild-wars%C2%AE-reforged/net.arena.guildwars.reforged); its XAPK SHA256 is `8f66df0b4703835f05918792f6ef072f7bedaeebe571b354d3e2bf3698f6472e`.

The base APK signature was verified with Android SDK `apksigner`. The importer pins the recorded retail signing certificate, checks the package name and Steam configuration, and records the base APK and original loader hashes in [retail-client.json](retail-client.json). Extract the base APK from a retail XAPK or pull it from the installed retail app; split APKs are not required for the web assets.

```powershell
python tools\import_retail_mobile_client.py C:\path\to\net.arena.guildwars.reforged.apk
```

The importer preserves the existing generated Minimalus texture prelude, updates the retail asset graph, restores the local patch proxy and game-script texture hook, and connects the Steam bridge before the game starts. It stops if those upstream integration points or the Steam configuration have changed. It does not regenerate textures. Use `build_minimalus_mobile_app.py` for texture changes.

## Android flow

`minimalus-steam.js` wraps the retail login interface and passes Steam requests to `MainActivity`. Interactive requests open `SteamLoginActivity`, whose WebView has no native JavaScript bridge. It accepts a token only from the exact retail HTTPS callback and checks a freshly generated 256-bit OAuth state. It rejects ambiguous parameters and invalid callbacks. Steam pages never replace the game WebView.

`SteamAccountStore` encrypts tokens using AES-GCM and a device Android Keystore key. Cached sign-in respects expiration. Logout removes the cached credential and cancels an outstanding sign-in. Steam credentials are not stored in browser localStorage or written to logs. The live game engine still dispatches logout through its older `nativeAccount` interface; the game-script compatibility hook redirects that callback to `Module.login` so the Steam cache is cleared.

## Checks

```powershell
node --test tools\test_steam_bridge.cjs
python tools\verify_mobile_client.py
gradle assembleDebug testDebugUnitTest lintDebug
```

To check a freshly downloaded, hash-verified live `Gw.js` against the texture and login hooks:

```powershell
node tools\verify_live_runtime.cjs C:\path\to\Gw.js
```

Local checks cover valid and invalid OAuth callbacks, login token shape, silent sign-in requests, cancellation and retries, logout, account switching, native storage errors, JavaScript syntax, and the shipped module graph. The complete 135-entry Minimalus texture prelude is preserved. The new APK uses versionCode 106 and the same local debug signing certificate as public 1.0.5, allowing an upgrade without uninstalling on devices with that release.

No Android device was connected for this update. A complete live Steam sign-in, Steam Guard, reconnect, and rendering pass must still be checked on a device using [the release checklist](release-checklist.md). This is a candidate build; the previously verified public 1.0.5 remains the latest release until device checks are complete.
