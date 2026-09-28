"""Check the shipped asset graph, Steam contract, and Minimalus texture integration."""

from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "app/src/main/assets/public"


def main():
    client = (PUBLIC / "astro/client-main.js").read_text(encoding="utf-8")
    table_match = re.search(r"window\.__gwMinimalusReplacements=(\{.*?\});", client, re.S)
    if not table_match:
        raise ValueError("Missing texture table")
    table = json.loads(table_match.group(1))
    assert table and any(entry.get("source") == "mobile" for entry in table.values()), "Missing mobile texture overrides"
    assert "window.__gwPatchGwJs(new TextDecoder().decode(minimalusSource))" in client, "Game-script texture hook missing"
    assert "window.MinimalusSteam.wrapLogin(" in client, "Native Steam adapter missing"
    assert "window.MinimalusSteam.patchClientSource(minimalusSource)" in client, "Game logout adapter missing"
    assert 'oauth2.Steam={clientId:"CE9BDCEC"' in client, "Retail Steam provider missing"
    assert '"https://minimalus.local/gwpatch"' in client, "Patch proxy missing"
    index = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert index.index('src="/minimalus-steam.js"') < index.index('src="/astro/client-main.js"'), "Steam adapter must load before the game"
    javascript = list(PUBLIC.rglob("*.js"))
    references = 0
    for file in javascript:
        source = file.read_text(encoding="utf-8")
        for match in re.finditer(r'["\'](\./[^"\']+\.js|astro/[^"\']+\.js)["\']', source):
            reference = match.group(1)
            target = file.parent / reference if reference.startswith("./") else PUBLIC / reference
            assert target.is_file(), f"Missing module {reference} from {file.name}"
            references += 1
        result = subprocess.run(["node", "--input-type=module", "--check"], input=source, text=True,
            encoding="utf-8", capture_output=True)
        if result.returncode:
            raise ValueError(f"Javascript syntax error in {file.name}: {result.stderr}")
    print(f"Verified {len(javascript)} scripts, {references} module references, {len(table)} texture replacements, and Steam login wiring")


if __name__ == "__main__":
    main()
