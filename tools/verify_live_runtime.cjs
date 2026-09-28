"use strict";
// Run only on a Gw.js fetched from the retail patch manifest with verified chunk hashes.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

async function main() {
  if (!process.argv[2]) throw new Error("Usage: node tools/verify_live_runtime.cjs path/to/Gw.js");
  const runtime = fs.readFileSync(process.argv[2], "utf8");
  const client = fs.readFileSync(path.join(__dirname, "../app/src/main/assets/public/astro/client-main.js"), "utf8");
  const prelude = client.slice(0, client.indexOf("const __vite__mapDeps="));
  const window = { addEventListener() {} };
  const context = {
    window, console: { log() {}, warn() {}, error() {} }, performance: { now: () => 0 },
    document: { readyState: "complete" }, setTimeout() {}, setInterval() {},
    fetch: () => Promise.resolve({ ok: false }),
  };
  vm.runInNewContext(prelude, context);
  const texturePatched = window.__gwPatchGwJs(runtime);
  assert.notEqual(texturePatched, runtime, "No live texture hooks were applied");
  for (const kind of ["texImage2D", "texSubImage2D", "compressedTexSubImage2D", "texStorage2D"]) {
    assert.ok(texturePatched.includes("window.__gwTextureProbeEmscripten('" + kind + "'"), "Missing live hook: " + kind);
  }
  assert.ok(texturePatched.includes("boundTextureNamesByTarget.set(target, texture)"), "Missing texture binding hook");
  const nativeRequests = [];
  let nativeClears = 0;
  window.MinimalusNative = {
    startSteamLogin(id, silent) {
      nativeRequests.push({ id, silent });
      window.__minimalusSteamResult(id, { token: "fixture-steam-token" });
    },
    clearSteamAccount() { nativeClears++; },
    storeSteamAccount() { return true; },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../app/src/main/assets/public/minimalus-steam.js"), "utf8"), context);
  const login = window.MinimalusSteam.wrapLogin({
    hasProvider: provider => provider === "Steam",
    async clearAccountData() {},
  });
  const patched = window.MinimalusSteam.patchClientSource(texturePatched);
  const lines = patched.split(/\r?\n/);
  function callback(containing) {
    const line = lines.find(value => /^\s*\d+:/.test(value) && value.includes(containing));
    assert.ok(line, "Live game callback changed: " + containing);
    return line.slice(line.indexOf(":") + 1).trim().replace(/,\s*$/, "");
  }
  const memory = new Map();
  let pointer = 1;
  let result;
  const game = {
    Module: { login, nativeAccount: null },
    UTF16ToString: () => "Steam",
    lengthBytesUTF8: value => Buffer.byteLength(value),
    _malloc: () => pointer++, _free() {},
    stringToUTF8: (value, ptr) => memory.set(ptr, value),
    _EmscriptenGcPlatformGetAuthTokenResult: (...values) => { result = values; },
  };
  assert.equal(vm.runInNewContext("(" + callback("Module.login.hasProvider") + ")", game)(0), 1);
  vm.runInNewContext("(" + callback("Module.login.getAuthToken") + ")", game)(0, 37, 1, 91);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(nativeRequests.length, 1);
  assert.equal(nativeRequests[0].silent, true);
  assert.deepEqual(result.slice(0, 3), [37, 0, 0]);
  assert.equal(memory.get(result[3]), "fixture-steam-token");
  assert.equal(result[4], 91);
  vm.runInNewContext("(" + callback("Module.login.clearAccountData") + ")", game)();
  assert.equal(nativeClears, 1, "Live game logout did not clear native Steam credentials");
  console.log("Verified 5 texture hooks and the live engine's Steam provider, token return, silent flag, and logout callbacks");
}

main().catch(error => { console.error(error); process.exitCode = 1; });
