package com.minimalus.mobile.v1;

import java.net.URI;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.security.SecureRandom;
import java.text.ParsePosition;
import java.text.SimpleDateFormat;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;

/** Steam configuration shipped in the retail mobile client 1.1.7. */
final class SteamOAuth {
    static final String REDIRECT_URL = "https://www.guildwars.com/app/live/auth";
    static final long TOKEN_LIFETIME_MS = 31536000L * 1000L;

    static String newState() {
        byte[] bytes = new byte[32];
        new SecureRandom().nextBytes(bytes);
        StringBuilder state = new StringBuilder();
        for (byte value : bytes) state.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return state.toString();
    }

    static String authorizationUrl(String state) {
        try {
            return "https://steamcommunity.com/oauth/login?client_id=CE9BDCEC"
                + "&response_type=token&redirect_uri=" + URLEncoder.encode(REDIRECT_URL, "UTF-8")
                + "&state=" + URLEncoder.encode(state, "UTF-8");
        } catch (java.io.UnsupportedEncodingException impossible) {
            throw new AssertionError(impossible);
        }
    }

    static boolean isCallback(String url) {
        try {
            URI uri = new URI(url);
            return "https".equalsIgnoreCase(uri.getScheme())
                && "www.guildwars.com".equalsIgnoreCase(uri.getHost())
                && uri.getRawUserInfo() == null && (uri.getPort() == -1 || uri.getPort() == 443)
                && "/app/live/auth".equals(uri.getRawPath());
        } catch (Exception invalid) {
            return false;
        }
    }

    static String tokenFromCallback(String url, String expectedState) throws Exception {
        if (!isCallback(url)) throw new IllegalArgumentException("Unexpected Steam redirect.");
        URI uri = new URI(url);
        Map<String, String> fields = new HashMap<>();
        addFields(fields, uri.getRawQuery());
        addFields(fields, uri.getRawFragment());
        if (expectedState == null || expectedState.isEmpty() || !expectedState.equals(fields.get("state"))) {
            throw new IllegalArgumentException("Steam sign-in state did not match. Please try again.");
        }
        if (fields.containsKey("error")) {
            throw new IllegalArgumentException("Steam declined or cancelled sign-in.");
        }
        String token = fields.get("access_token");
        if (token == null || token.isEmpty()) throw new IllegalArgumentException("Steam returned no access token.");
        return token;
    }

    private static void addFields(Map<String, String> fields, String encoded) throws Exception {
        if (encoded == null || encoded.isEmpty()) return;
        for (String pair : encoded.split("&")) {
            String[] parts = pair.split("=", 2);
            String name = URLDecoder.decode(parts[0], "UTF-8");
            String value = parts.length == 2 ? URLDecoder.decode(parts[1], "UTF-8") : "";
            if (fields.containsKey(name)) throw new IllegalArgumentException("Ambiguous Steam redirect.");
            fields.put(name, value);
        }
    }

    static long expirationMillis(String isoDate) {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ROOT);
        format.setLenient(false);
        format.setTimeZone(TimeZone.getTimeZone("UTC"));
        ParsePosition position = new ParsePosition(0);
        java.util.Date date = format.parse(isoDate, position);
        if (date == null || position.getIndex() != isoDate.length()) {
            throw new IllegalArgumentException("Invalid Steam account expiration.");
        }
        return date.getTime();
    }
}
