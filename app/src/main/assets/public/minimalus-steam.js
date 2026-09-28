(function () {
  "use strict";
  const pending = new Map();
  let sequence = 0;

  function cancelPending() {
    const error = new Error("Steam sign-in cancelled.");
    error.code = "USER_CANCELLED";
    for (const request of pending.values()) request.reject(error);
    pending.clear();
  }

  window.__minimalusSteamResult = function (id, result) {
    const request = pending.get(id);
    if (!request) return;
    pending.delete(id);
    if (result.error) {
      const error = new Error(result.message || "Steam sign-in failed.");
      error.code = result.error;
      request.reject(error);
    } else if (typeof result.token !== "string" || !result.token) {
      request.reject(new Error("Steam returned no access token."));
    } else {
      // This is the token shape expected by the retail 1.1.7 mobile game client.
      request.resolve({ refreshToken: result.token });
    }
  };

  window.MinimalusSteam = {
    patchClientSource: function (source) {
      // The live Gw.js engine still dispatches logout through nativeAccount,
      // while the updated loader exposes Steam sessions through Module.login.
      const legacyLogout = "if (Module.nativeAccount && typeof Module.nativeAccount.clearAccountData === 'function') { Module.nativeAccount.clearAccountData(); }";
      const logout = "if (Module.login && typeof Module.login.clearAccountData === 'function') { Module.login.clearAccountData(); } else { " + legacyLogout + " }";
      return source.replace(legacyLogout, logout);
    },
    wrapLogin: function (login) {
      const native = window.MinimalusNative;
      if (!native || !native.startSteamLogin) return login;
      let steamActive = false;
      const wrapped = Object.create(login);
      wrapped.getAuthToken = function (provider, options) {
        if (provider !== "Steam") {
          cancelPending();
          steamActive = false;
          native.clearSteamAccount();
          return login.getAuthToken(provider, options);
        }
        if (pending.size) return Promise.reject(new Error("Steam sign-in is already in progress."));
        const id = "steam-" + (++sequence);
        return new Promise(function (resolve, reject) {
          pending.set(id, { resolve: resolve, reject: reject });
          try { native.startSteamLogin(id, !!(options && options.silent)); }
          catch (error) { pending.delete(id); reject(error); }
        }).then(function (token) {
          steamActive = true;
          return token;
        }, function (error) {
          steamActive = false;
          throw error;
        });
      };
      wrapped.storeAccountData = async function (token, expiration) {
        if (!steamActive) return login.storeAccountData(token, expiration);
        if (!native.storeSteamAccount(token, expiration.toISOString())) {
          throw new Error("Could not save Steam account on this device.");
        }
      };
      wrapped.clearAccountData = async function () {
        cancelPending();
        native.clearSteamAccount();
        steamActive = false;
        return login.clearAccountData();
      };
      return wrapped;
    }
  };
})();
