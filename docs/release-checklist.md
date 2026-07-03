# Release Checklist

Use this before promoting a beta APK to stable.

- Build a fresh APK from a clean checkout.
- Install from a browser download, not only through `adb install`.
- Confirm login reaches the live game world.
- Confirm `logcat` shows the expected Minimalus replacement count.
- Restart the app and confirm login/session behavior.
- Reboot the Android device and launch again.
- Visit login, character select, inventory, skills, party, map, chat, merchant, and combat HUD surfaces.
- Confirm mobile-specific textures override PC sister textures.
- Record APK SHA256 in the GitHub release notes.
