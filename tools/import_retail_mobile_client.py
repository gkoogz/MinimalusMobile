"""Import a signed retail APK while preserving Minimalus's generated texture hooks.

This does not download or install an APK. Supply a retail base APK; split resource
APKs are not needed. Android SDK build-tools verify its signer and read its version.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "app/src/main/assets/public"
RETAIL_SIGNER_SHA256 = "1722268de1907f1dcd0669d72634d43d010608b1d7f92fe858fabc123dfaff6b"


def sdk_tool(name):
    installed = shutil.which(name)
    if installed:
        return installed
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk and os.name == "nt":
        sdk = str(Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk")
    extension = ".bat" if name == "apksigner" and os.name == "nt" else ".exe" if os.name == "nt" else ""
    matches = sorted((Path(sdk or "") / "build-tools").glob("*/" + name + extension), reverse=True)
    if not matches:
        raise RuntimeError(f"Android SDK tool {name} is required; set ANDROID_HOME.")
    return str(matches[0])


def run_tool(name, *args):
    result = subprocess.run([sdk_tool(name), *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{name} failed: {result.stderr.strip()}")
    return result.stdout


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Retail client hook changed: {old[:80]}")
    return source.replace(old, new, 1)


def adapt_client(source, prelude):
    # Keep the retail version check: the WebView platform naturally skips the
    # retail Play Store check, while native retail clients still use their check.
    source = replace_once(source, '"https://patching.1.arenanetworks.com"', '"https://minimalus.local/gwpatch"')
    module = re.search(r"window\.Module=([A-Za-z_$][\w$]*);", source)
    if not module:
        raise ValueError("Retail client Module assignment changed.")
    name = module.group(1)
    source = replace_once(source, module.group(0),
        f"{name}.login=window.MinimalusSteam.wrapLogin({name}.login);" + module.group(0))
    loader = re.compile(
        r'const (?P<data>\w+)=await (?P<image>\w+)\.load\((?P<script>\w+),'
        r'(?P<progress>\([^;]*?\)=>\{[^;]*?\})\),'
        r'(?P<blob>\w+)=new Blob\(\[(?P=data)\],\{type:"application/javascript"\}\);'
    )

    def inject(match):
        values = match.groupdict()
        return (
            f"const {values['data']}=await {values['image']}.load({values['script']},{values['progress']});"
            f"let minimalusSource={values['data']};"
            "if(window.__gwPatchGwJs)minimalusSource=window.__gwPatchGwJs(new TextDecoder().decode(minimalusSource));"
            "minimalusSource=window.MinimalusSteam.patchClientSource(minimalusSource);"
            f"const {values['blob']}=new Blob([minimalusSource],{{type:\"application/javascript\"}});"
        )

    source, count = loader.subn(inject, source)
    if count != 1:
        raise ValueError("Retail game-script loader changed; texture hook was not applied.")
    return prelude + source


def prepare_assets(apk, existing_client):
    marker = existing_client.find("const __vite__mapDeps=")
    if marker < 0 or "window.__gwMinimalusReplacements=" not in existing_client[:marker]:
        raise ValueError("Cannot find existing Minimalus texture prelude.")
    prelude = existing_client[:marker]
    with zipfile.ZipFile(apk) as archive:
        public_names = [entry.filename for entry in archive.infolist()
            if entry.filename.startswith("assets/public/") and not entry.is_dir()]
        if len(public_names) != len(set(public_names)):
            raise ValueError("Duplicate public assets in APK.")
        mains = [name for name in public_names if re.fullmatch(
            r"assets/public/_astro/Client\.astro_astro_type_script_index_0_lang\.[\w-]+\.js", name)]
        if len(mains) != 1:
            raise ValueError("Expected exactly one retail client entry point.")
        retail_main = PurePosixPath(mains[0]).name
        source_main = archive.read(mains[0])
        source = source_main.decode("utf-8")
        for expected in ['oauth2.Steam=', 'clientId:"CE9BDCEC"',
                'authorizationBaseUrl:"https://steamcommunity.com/oauth/login"',
                'redirectUrl:"https://www.guildwars.com/app/live/auth"', 'responseType:"token"']:
            if expected not in source:
                raise ValueError("Steam login contract changed or is absent: " + expected)
        assets = {}
        for name in public_names:
            relative = PurePosixPath(name.removeprefix("assets/public/"))
            if ".." in relative.parts or relative.is_absolute() or "\\" in name:
                raise ValueError("Invalid APK asset path.")
            target = relative.as_posix().replace("_astro/", "astro/").replace(retail_main, "client-main.js")
            data = archive.read(name)
            if relative.suffix in {".js", ".html", ".json", ".webmanifest", ".css"}:
                text = data.decode("utf-8").replace("_astro/", "astro/").replace(retail_main, "client-main.js")
                if name == mains[0]:
                    text = adapt_client(text, prelude)
                if target == "index.html":
                    text = replace_once(text, '<script type="module" src="/astro/client-main.js">',
                        '<script src="/minimalus-steam.js"></script><script type="module" src="/astro/client-main.js">')
                data = text.encode("utf-8")
            if target in assets:
                raise ValueError("Duplicate mapped asset path: " + target)
            assets[target] = data
    return assets, hashlib.sha256(source_main).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    args = parser.parse_args()
    certificate = run_tool("apksigner", "verify", "--print-certs", args.apk)
    fingerprints = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)", certificate)
    if fingerprints != [RETAIL_SIGNER_SHA256]:
        raise ValueError("APK signer differs from the retail Guild Wars mobile signer.")
    badging = run_tool("aapt", "dump", "badging", args.apk)
    package = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", badging)
    if not package or package.group(1) != "net.arena.guildwars.reforged":
        raise ValueError("APK is not Guild Wars Reforged mobile.")
    existing = (PUBLIC / "astro/client-main.js").read_text(encoding="utf-8")
    assets, source_hash = prepare_assets(args.apk, existing)
    # Validation above finishes before any checked-in asset is replaced.
    for name, data in assets.items():
        target = PUBLIC / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for directory in (PUBLIC / "astro", PUBLIC / "plugins"):
        for target in directory.rglob("*"):
            if target.is_file() and target.relative_to(PUBLIC).as_posix() not in assets:
                target.unlink()
    metadata = {
        "package": package.group(1), "version": package.group(3), "versionCode": int(package.group(2)),
        "apkSha256": hashlib.sha256(args.apk.read_bytes()).hexdigest(),
        "signerSha256": RETAIL_SIGNER_SHA256, "sourceClientSha256": source_hash,
        "clientAssetCount": len(assets),
        "steamClientId": "CE9BDCEC", "steamRedirectUrl": "https://www.guildwars.com/app/live/auth",
    }
    (ROOT / "docs/retail-client.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Imported retail mobile {package.group(3)} ({package.group(2)}): {len(assets)} assets")


if __name__ == "__main__":
    main()
