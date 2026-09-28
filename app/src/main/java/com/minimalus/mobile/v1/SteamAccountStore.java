package com.minimalus.mobile.v1;

import android.content.Context;
import android.annotation.SuppressLint;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONObject;

import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** The Steam bearer token never goes into WebView localStorage or plain preferences. */
final class SteamAccountStore {
    private static final String KEY_ALIAS = "MinimalusSteamAccount";
    private final SharedPreferences preferences;

    SteamAccountStore(Context context) {
        preferences = context.getSharedPreferences("steam_account", Context.MODE_PRIVATE);
    }

    private SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(KEY_ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(KEY_ALIAS, null);
    }

    synchronized void save(String token, long expiresAt) throws Exception {
        if (token == null || token.isEmpty() || expiresAt <= System.currentTimeMillis()) {
            throw new IllegalArgumentException("Invalid Steam account data.");
        }
        JSONObject account = new JSONObject();
        account.put("token", token);
        account.put("expiresAt", expiresAt);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] encrypted = cipher.doFinal(account.toString().getBytes("UTF-8"));
        JSONObject envelope = new JSONObject();
        envelope.put("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP));
        envelope.put("data", Base64.encodeToString(encrypted, Base64.NO_WRAP));
        if (!preferences.edit().putString("account", envelope.toString()).commit()) {
            throw new java.io.IOException("Could not save Steam account.");
        }
    }

    synchronized String load() {
        String saved = preferences.getString("account", null);
        if (saved == null) return null;
        try {
            JSONObject envelope = new JSONObject(saved);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128,
                Base64.decode(envelope.getString("iv"), Base64.NO_WRAP)));
            byte[] plain = cipher.doFinal(Base64.decode(envelope.getString("data"), Base64.NO_WRAP));
            JSONObject account = new JSONObject(new String(plain, "UTF-8"));
            String token = account.getString("token");
            if (!token.isEmpty() && account.getLong("expiresAt") > System.currentTimeMillis()) return token;
        } catch (Exception unreadable) {
            // A removed or invalidated device key requires a fresh interactive sign-in.
        }
        clear();
        return null;
    }

    // Finish removing the credential before another silent login can read it.
    @SuppressLint("ApplySharedPref")
    synchronized void clear() {
        preferences.edit().remove("account").commit();
    }
}
