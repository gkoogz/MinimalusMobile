package com.minimalus.mobile.v1;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;

/** Separate from the game WebView, with no JavascriptInterface available to sign-in pages. */
public class SteamLoginActivity extends Activity {
    private WebView authView;
    private String state;
    private boolean completed;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        state = savedInstanceState == null ? SteamOAuth.newState() : savedInstanceState.getString("oauthState");
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        Button cancel = new Button(this);
        cancel.setText(R.string.cancel_steam_signin);
        cancel.setOnClickListener(view -> finish());
        layout.addView(cancel);
        authView = new WebView(this);
        WebSettings settings = authView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSaveFormData(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(authView, true);
        authView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return false;
                String url = request.getUrl().toString();
                if (consumeCallback(url)) return true;
                Uri uri = request.getUrl();
                String host = uri.getHost();
                boolean steamHost = host != null && (host.equals("steamcommunity.com")
                    || host.endsWith(".steamcommunity.com") || host.equals("steampowered.com")
                    || host.endsWith(".steampowered.com"));
                if ("https".equalsIgnoreCase(uri.getScheme()) && steamHost) return false;
                if ("steam".equalsIgnoreCase(uri.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (android.content.ActivityNotFoundException unavailable) { /* Stay on the Steam page. */ }
                    return true;
                }
                return true;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                if (consumeCallback(url)) view.stopLoading();
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                consumeCallback(url);
            }
        });
        layout.addView(authView, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(layout);
        if (savedInstanceState == null || authView.restoreState(savedInstanceState) == null) {
            authView.loadUrl(SteamOAuth.authorizationUrl(state));
        }
    }

    private boolean consumeCallback(String url) {
        if (!SteamOAuth.isCallback(url)) return false;
        if (completed || isFinishing()) return true;
        completed = true;
        Intent result = new Intent();
        try {
            String token = SteamOAuth.tokenFromCallback(url, state);
            new SteamAccountStore(this).save(token, System.currentTimeMillis() + SteamOAuth.TOKEN_LIFETIME_MS);
            result.putExtra("token", token);
            setResult(RESULT_OK, result);
        } catch (Exception invalid) {
            // Do not return exception details that could include the credential-bearing redirect URL.
            result.putExtra("error", "Steam sign-in could not be completed. Please try again.");
            setResult(RESULT_CANCELED, result);
        }
        finish();
        return true;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        outState.putString("oauthState", state);
        authView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    protected void onDestroy() {
        if (authView != null) authView.destroy();
        super.onDestroy();
    }
}
