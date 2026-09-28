package com.minimalus.mobile.v1;

import org.junit.Test;

import static org.junit.Assert.*;

public class SteamOAuthTest {
    private static final String STATE = "expected-session";

    @Test
    public void consumesImplicitGrantTokenInFragment() throws Exception {
        assertEquals("test+token/==", SteamOAuth.tokenFromCallback(SteamOAuth.REDIRECT_URL
            + "#access_token=test%2Btoken%2F%3D%3D&token_type=bearer&state=" + STATE, STATE));
    }

    @Test
    public void consumesTokenAndStateAcrossQueryAndFragment() throws Exception {
        assertEquals("test-token", SteamOAuth.tokenFromCallback(SteamOAuth.REDIRECT_URL
            + "?state=" + STATE + "#access_token=test-token", STATE));
    }

    @Test
    public void rejectsForeignAndLookalikeRedirects() {
        for (String url : new String[] {
            "http://www.guildwars.com/app/live/auth", "https://www.guildwars.com.evil.test/app/live/auth",
            "https://www.guildwars.com@evil.test/app/live/auth", "https://user@www.guildwars.com/app/live/auth",
            "https://www.guildwars.com:444/app/live/auth", "https://www.guildwars.com/app/live/auth/extra",
            "https://www.guildwars.com/app/live/%61uth", "https://evil.test/app/live/auth"
        }) {
            assertFalse(url, SteamOAuth.isCallback(url));
        }
    }

    @Test
    public void rejectsMissingMismatchedAndDuplicateState() {
        for (String fields : new String[] {
            "access_token=test-token", "access_token=test-token&state=wrong-session",
            "access_token=test-token&state=" + STATE + "&state=" + STATE,
            "access_token=test-token&state=" + STATE + "&access_token=other-token"
        }) {
            assertThrows(Exception.class, () -> SteamOAuth.tokenFromCallback(SteamOAuth.REDIRECT_URL + "#" + fields, STATE));
        }
        assertThrows(Exception.class, () -> SteamOAuth.tokenFromCallback(
            SteamOAuth.REDIRECT_URL + "?state=" + STATE + "#state=" + STATE + "&access_token=test-token", STATE));
    }

    @Test
    public void rejectsCancellationMissingAndMalformedTokens() {
        for (String fields : new String[] {
            "error=access_denied", "access_token=", "code=not-an-implicit-token", "access_token=%XX"
        }) {
            assertThrows(Exception.class, () -> SteamOAuth.tokenFromCallback(
                SteamOAuth.REDIRECT_URL + "#state=" + STATE + "&" + fields, STATE));
        }
    }

    @Test
    public void usesRetailImplicitGrantConfigurationAndFreshState() {
        String first = SteamOAuth.newState();
        String second = SteamOAuth.newState();
        assertNotEquals(first, second);
        assertTrue(first.matches("[a-f0-9]{64}"));
        String url = SteamOAuth.authorizationUrl(first);
        assertTrue(url.startsWith("https://steamcommunity.com/oauth/login?"));
        assertTrue(url.contains("client_id=CE9BDCEC"));
        assertTrue(url.contains("response_type=token"));
        assertTrue(url.contains("redirect_uri=https%3A%2F%2Fwww.guildwars.com%2Fapp%2Flive%2Fauth"));
        assertTrue(url.endsWith("&state=" + first));
    }

    @Test
    public void parsesJavascriptExpirationInUtcAndRejectsTrailingOrInvalidDates() {
        assertEquals(1790812800123L, SteamOAuth.expirationMillis("2026-10-01T00:00:00.123Z"));
        assertEquals("2026-10-01T00:00:00.123Z", SteamOAuth.expirationIsoDate(1790812800123L));
        assertEquals(1790812800123L, SteamOAuth.expirationMillis(SteamOAuth.expirationIsoDate(1790812800123L)));
        assertThrows(IllegalArgumentException.class, () -> SteamOAuth.expirationMillis("2026-02-30T00:00:00.000Z"));
        assertThrows(IllegalArgumentException.class, () -> SteamOAuth.expirationMillis("2026-10-01T00:00:00.000Zextra"));
    }
}
