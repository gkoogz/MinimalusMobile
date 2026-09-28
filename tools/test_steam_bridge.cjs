"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../app/src/main/assets/public/minimalus-steam.js"), "utf8");

function setup(withNative = true) {
  const requests = [];
  const calls = [];
  const window = {};
  const native = {
    startSteamLogin(id, silent) { requests.push({ id, silent }); },
    clearSteamAccount() { calls.push("clear-native"); },
    storeSteamAccount(token, expiration) { calls.push(["store-native", token, expiration]); return true; }
  };
  if (withNative) window.MinimalusNative = native;
  vm.runInNewContext(source, { window });
  const retail = {
    hasProvider(name) { return name === "Steam"; },
    async getAuthToken(name) { calls.push(["retail-login", name]); return { authCode: "retail-token" }; },
    async storeAccountData(token) { calls.push(["store-retail", token]); },
    async clearAccountData() { calls.push("clear-retail"); }
  };
  const login = window.MinimalusSteam.wrapLogin(retail);
  function reply(result) { window.__minimalusSteamResult(requests.at(-1).id, result); }
  return { window, native, requests, calls, retail, login, reply };
}

test("Steam native result supplies the game's refreshToken and keeps silent requests silent", async () => {
  const env = setup();
  assert.equal(env.login.hasProvider("Steam"), true);
  const pending = env.login.getAuthToken("Steam", { silent: true });
  assert.equal(env.requests[0].silent, true);
  env.reply({ token: "fixture-steam-token" });
  assert.equal((await pending).refreshToken, "fixture-steam-token");
  assert.equal(env.calls.length, 0);
  await env.login.storeAccountData("fixture-updated-token", new Date("2027-01-01T00:00:00.000Z"));
  assert.deepEqual(env.calls[0], ["store-native", "fixture-updated-token", "2027-01-01T00:00:00.000Z"]);
});

test("cancelling sign-in permits a retry and leaves retail account storage usable", async () => {
  const env = setup();
  const pending = env.login.getAuthToken("Steam", {});
  env.reply({ error: "USER_CANCELLED", message: "Cancelled" });
  await assert.rejects(pending, { code: "USER_CANCELLED" });
  await env.login.storeAccountData("retail-session", new Date());
  assert.deepEqual(env.calls[0], ["store-retail", "retail-session"]);
  const retry = env.login.getAuthToken("Steam", {});
  env.reply({ token: "new-session" });
  assert.equal((await retry).refreshToken, "new-session");
});

test("no cached account, invalid token, and native failure settle requests without blocking retry", async () => {
  const env = setup();
  const noCache = env.login.getAuthToken("Steam", { silent: true });
  env.reply({ error: "NO_CACHED_ACCOUNT" });
  await assert.rejects(noCache, { code: "NO_CACHED_ACCOUNT" });
  const empty = env.login.getAuthToken("Steam", {});
  env.reply({ token: "" });
  await assert.rejects(empty, /no access token/);
  env.native.startSteamLogin = () => { throw new Error("native unavailable"); };
  await assert.rejects(env.login.getAuthToken("Steam", {}), /native unavailable/);
});

test("concurrent Steam requests do not open a second sign-in screen", async () => {
  const env = setup();
  const first = env.login.getAuthToken("Steam", {});
  await assert.rejects(env.login.getAuthToken("Steam", {}), /already in progress/);
  assert.equal(env.requests.length, 1);
  env.reply({ token: "one-session" });
  await first;
});

test("logout cancels pending sign-in and ignores its late result", async () => {
  const env = setup();
  const pending = env.login.getAuthToken("Steam", {});
  const rejected = assert.rejects(pending, { code: "USER_CANCELLED" });
  await env.login.clearAccountData();
  await rejected;
  env.reply({ token: "obsolete-session" });
  assert.deepEqual(env.calls, ["clear-native", "clear-retail"]);
  const retry = env.login.getAuthToken("Steam", {});
  env.reply({ token: "new-session" });
  assert.equal((await retry).refreshToken, "new-session");
});

test("native storage failure is surfaced instead of storing bearer tokens in the web fallback", async () => {
  const env = setup();
  const pending = env.login.getAuthToken("Steam", {});
  env.reply({ token: "fixture-token" });
  await pending;
  env.native.storeSteamAccount = () => false;
  await assert.rejects(env.login.storeAccountData("fixture-token", new Date()), /Could not save/);
  assert.equal(env.calls.length, 0);
});

test("other providers retain their retail login path and clear the native Steam account", async () => {
  const env = setup();
  assert.equal((await env.login.getAuthToken("Google", {})).authCode, "retail-token");
  assert.deepEqual(env.calls, ["clear-native", ["retail-login", "Google"]]);
});

test("browser use without the Android bridge retains the retail login object", () => {
  const env = setup(false);
  assert.equal(env.login, env.retail);
});

test("legacy live-game logout clears the native Steam session through Module.login", async () => {
  const env = setup();
  const login = env.login.getAuthToken("Steam", {});
  env.reply({ token: "fixture-steam-token" });
  await login;
  // This callback is the legacy account ABI shipped by the live mobile engine.
  const engineCallback = "(() => { if (Module.nativeAccount && typeof Module.nativeAccount.clearAccountData === 'function') { Module.nativeAccount.clearAccountData(); } })()";
  const patched = env.window.MinimalusSteam.patchClientSource(engineCallback);
  vm.runInNewContext(patched, { Module: { login: env.login, nativeAccount: null } });
  await Promise.resolve();
  assert.deepEqual(env.calls, ["clear-native", "clear-retail"]);
});

test("switching to another provider cancels an in-flight Steam request", async () => {
  const env = setup();
  const pending = env.login.getAuthToken("Steam", {});
  const rejected = assert.rejects(pending, { code: "USER_CANCELLED" });
  await env.login.getAuthToken("Google", {});
  await rejected;
  env.reply({ token: "late-token" });
  await env.login.storeAccountData("retail-session", new Date());
  assert.deepEqual(env.calls.at(-1), ["store-retail", "retail-session"]);
});
