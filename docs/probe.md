# Mobile Texture Probe

The texture probe exists to rediscover native Android-only texture variants when the Windows mobile-layout dump is not enough.

## Start

```powershell
python tools\mobile_texture_bridge.py
adb reverse tcp:8787 tcp:8787
```

Then open:

```text
http://127.0.0.1:8787
```

## Workflow

1. Launch Minimalus Mobile on the connected Android device.
2. Use **Fresh Capture** to clear Android-side probe state and start capture.
3. Navigate in-game to the UI surface you want to inspect.
4. Use **Preview Selected**, **Next**, and **Prev** in the bridge UI.
5. Use **Dump Selected** only for textures you actually want to edit.
6. Edit the dumped DDS and place the altered version into `AlteredMobile`.
7. Run `python tools\build_minimalus_mobile_app.py`.
8. Rebuild the APK.

## Notes

The current probe is useful but rough. Text textures are noisy, and long capture sessions can accumulate irrelevant records. Reset between sessions and prefer targeted UI screens.
