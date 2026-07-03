package com.minimalus.mobile.v1;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.MimeTypeMap;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.JavascriptInterface;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;

public class MainActivity extends Activity {
    private static final String LOCAL_ORIGIN = "https://minimalus.local/";
    private static final String PATCH_HOST = "patching.1.arenanetworks.com";
    private static final String PATCH_PREFIX = "/gwpatch";
    private static final String ACCESS_KEY = "2043FE79-F32D-4FD7-8C27-0D47231C4F03";
    private static final String TAG = "MinimalusV1";
    private WebView webView;
    private String bridgeUserAgent = "MinimalusMobile/1.0";
    private final Map<String, String> webgateCookies = new LinkedHashMap<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        WebView.setWebContentsDebuggingEnabled(true);
        android.util.Log.i(TAG, "Starting Minimalus Mobile v1");
        webView = new WebView(this);
        configureWebView(webView);
        setContentView(webView);
        enterImmersiveMode();
        webView.loadUrl(LOCAL_ORIGIN);
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterImmersiveMode();
        if (webView != null) webView.onResume();
    }

    @Override
    protected void onPause() {
        if (webView != null) webView.onPause();
        super.onPause();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    private void configureWebView(WebView view) {
        WebSettings settings = view.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        bridgeUserAgent = settings.getUserAgentString() + " MinimalusMobile/1.0";
        settings.setUserAgentString(bridgeUserAgent);

        view.addJavascriptInterface(new MinimalusBridge(), "MinimalusNative");
        view.setWebViewClient(new LocalAssetClient());
        view.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {
                android.util.Log.i("MinimalusWeb", message.message() + " @" + message.sourceId() + ":" + message.lineNumber());
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                request.grant(request.getResources());
            }
        });
    }

    private void enterImmersiveMode() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        );
    }

    private static String mimeForPath(String path) {
        if (path.endsWith(".js")) return "application/javascript";
        if (path.endsWith(".css")) return "text/css";
        if (path.endsWith(".html")) return "text/html";
        if (path.endsWith(".svg")) return "image/svg+xml";
        if (path.endsWith(".wasm")) return "application/wasm";
        if (path.endsWith(".json") || path.endsWith(".webmanifest")) return "application/json";
        String ext = MimeTypeMap.getFileExtensionFromUrl(path);
        String mime = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        return mime != null ? mime : "application/octet-stream";
    }

    private static WebResourceResponse responseForStream(String mime, InputStream stream) {
        Map<String, String> headers = new HashMap<>();
        headers.put("Access-Control-Allow-Origin", LOCAL_ORIGIN.substring(0, LOCAL_ORIGIN.length() - 1));
        headers.put("Cache-Control", "no-store");
        return new WebResourceResponse(mime, null, 200, "OK", headers, stream);
    }

    private class LocalAssetClient extends WebViewClient {
        @Override
        public void onPageFinished(WebView view, String url) {
            android.util.Log.i(TAG, "Page finished: " + url);
            view.evaluateJavascript(webgateXhrShim(), null);
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            android.util.Log.e(TAG, "WebView error " + error.getErrorCode() + " " + error.getDescription() + " url=" + request.getUrl());
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri uri = request.getUrl();
            if (!"minimalus.local".equalsIgnoreCase(uri.getHost())) return null;

            String path = uri.getPath();
            if (path == null || path.equals("/")) path = "/index.html";
            if (path.equals(PATCH_PREFIX) || path.startsWith(PATCH_PREFIX + "/")) {
                return proxyPatchRequest(uri, path);
            }

            while (path.startsWith("/")) path = path.substring(1);
            String assetPath = "public/" + path;

            try {
                InputStream stream = getAssets().open(assetPath);
                android.util.Log.i(TAG, "Serving asset: " + assetPath);
                return responseForStream(mimeForPath(assetPath), stream);
            } catch (IOException ignored) {
                android.util.Log.e(TAG, "Missing asset: " + assetPath);
                return new WebResourceResponse("text/plain", "UTF-8", new java.io.ByteArrayInputStream(("missing " + assetPath).getBytes()));
            }
        }

        private WebResourceResponse proxyPatchRequest(Uri localUri, String localPath) {
            String remotePath = localPath.substring(PATCH_PREFIX.length());
            if (remotePath.length() == 0) remotePath = "/";

            try {
                Uri.Builder builder = new Uri.Builder()
                    .scheme("https")
                    .encodedAuthority(PATCH_HOST)
                    .encodedPath(remotePath);
                if (localUri.getEncodedQuery() != null) {
                    builder.encodedQuery(localUri.getEncodedQuery());
                }

                String remoteUrl = builder.build().toString();
                android.util.Log.i(TAG, "Proxying patch asset: " + remoteUrl);
                HttpURLConnection connection = (HttpURLConnection) new URL(remoteUrl).openConnection();
                connection.setRequestMethod("GET");
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(60000);
                connection.setRequestProperty("X-Access-Key", ACCESS_KEY);
                connection.setRequestProperty("Accept-Encoding", "identity");
                connection.setRequestProperty("User-Agent", "MinimalusMobile/1.0");
                connection.connect();

                int code = connection.getResponseCode();
                InputStream stream = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
                if (stream == null) {
                    stream = new java.io.ByteArrayInputStream(new byte[0]);
                }

                Map<String, String> headers = new HashMap<>();
                headers.put("Access-Control-Allow-Origin", LOCAL_ORIGIN.substring(0, LOCAL_ORIGIN.length() - 1));
                headers.put("Cache-Control", "no-store");
                String mime = connection.getContentType();
                if (mime == null || mime.length() == 0) mime = mimeForPath(remotePath);
                int semi = mime.indexOf(';');
                if (semi >= 0) mime = mime.substring(0, semi);
                return new WebResourceResponse(mime, null, code, connection.getResponseMessage(), headers, stream);
            } catch (Exception ex) {
                android.util.Log.e(TAG, "Patch proxy failed for " + localUri, ex);
                return new WebResourceResponse("text/plain", "UTF-8", new java.io.ByteArrayInputStream(("patch proxy failed: " + ex.getMessage()).getBytes()));
            }
        }
    }

    private class MinimalusBridge {
        @JavascriptInterface
        public String httpRequest(String method, String url, String headerLines, String body) {
            HttpURLConnection connection = null;
            try {
                if ((method == null || method.length() == 0 || "GET".equalsIgnoreCase(method)) && body != null && body.length() > 0) {
                    method = "POST";
                }
                android.util.Log.i(TAG, "Native HTTP bridge: " + method + " " + url + " bodyBytes=" + (body == null ? 0 : body.getBytes("UTF-8").length));
                connection = (HttpURLConnection) new URL(url).openConnection();
                connection.setRequestMethod(method);
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(10000);
                connection.setReadTimeout(15000);
                connection.setRequestProperty("Accept-Encoding", "identity");
                connection.setRequestProperty("Connection", "close");
                connection.setRequestProperty("User-Agent", bridgeUserAgent);
                String cookieHeader = cookieHeader();
                if (cookieHeader.length() > 0) {
                    connection.setRequestProperty("Cookie", cookieHeader);
                    android.util.Log.i(TAG, "Native HTTP bridge cookies=" + webgateCookies.size());
                }
                if (headerLines != null && headerLines.length() > 0) {
                    String[] lines = headerLines.split("\\n");
                    StringBuilder headerNames = new StringBuilder();
                    for (String line : lines) {
                        int sep = line.indexOf(':');
                        if (sep <= 0) continue;
                        String key = line.substring(0, sep).trim();
                        String value = line.substring(sep + 1).trim();
                        if (key.length() == 0) continue;
                        if ("origin".equalsIgnoreCase(key) || "referer".equalsIgnoreCase(key)) continue;
                        if ("user-agent".equalsIgnoreCase(key) || "host".equalsIgnoreCase(key)) continue;
                        connection.setRequestProperty(key, value);
                        if (headerNames.length() > 0) headerNames.append(",");
                        headerNames.append(key);
                    }
                    android.util.Log.i(TAG, "Native HTTP bridge requestHeaders=" + headerNames);
                }
                if (body != null && body.length() > 0) {
                    connection.setDoOutput(true);
                    byte[] bytes = body.getBytes("UTF-8");
                    if (connection.getRequestProperty("Content-Type") == null) {
                        String trimmed = body.trim();
                        connection.setRequestProperty(
                            "Content-Type",
                            trimmed.startsWith("<") ? "application/xml; charset=UTF-8" : "application/x-www-form-urlencoded; charset=UTF-8"
                        );
                    }
                    connection.setFixedLengthStreamingMode(bytes.length);
                    OutputStream output = connection.getOutputStream();
                    output.write(bytes);
                    output.flush();
                    output.close();
                }

                int code = connection.getResponseCode();
                android.util.Log.i(TAG, "Native HTTP bridge status: " + code + " " + connection.getResponseMessage());
                storeCookies(connection.getHeaderFields());
                InputStream input = code >= 400 ? connection.getErrorStream() : connection.getInputStream();
                String responseBody = input == null ? "" : readUtf8(input);
                String contentType = connection.getContentType();
                if (contentType == null) contentType = "text/xml";
                android.util.Log.i(TAG, "Native HTTP bridge responseBytes=" + responseBody.getBytes("UTF-8").length + " contentType=" + contentType);
                if (code >= 400 && responseBody.length() <= 512) {
                    android.util.Log.i(TAG, "Native HTTP bridge errorBody=" + responseBody.replace('\n', ' ').replace('\r', ' '));
                }
                return code + "\n" + contentType + "\n" + responseBody;
            } catch (Exception ex) {
                android.util.Log.e(TAG, "Native HTTP bridge failed for " + url, ex);
                return "599\ntext/plain\n" + ex.getMessage();
            } finally {
                if (connection != null) connection.disconnect();
            }
        }
    }

    private synchronized String cookieHeader() {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<String, String> entry : webgateCookies.entrySet()) {
            if (builder.length() > 0) builder.append("; ");
            builder.append(entry.getKey()).append("=").append(entry.getValue());
        }
        return builder.toString();
    }

    private synchronized void storeCookies(Map<String, List<String>> headerFields) {
        if (headerFields == null) return;
        for (Map.Entry<String, List<String>> entry : headerFields.entrySet()) {
            String key = entry.getKey();
            if (key == null || !"set-cookie".equalsIgnoreCase(key)) continue;
            List<String> cookies = entry.getValue();
            if (cookies == null) continue;
            for (String cookie : cookies) {
                if (cookie == null) continue;
                int semi = cookie.indexOf(';');
                String pair = semi >= 0 ? cookie.substring(0, semi) : cookie;
                int equals = pair.indexOf('=');
                if (equals <= 0) continue;
                String name = pair.substring(0, equals).trim();
                String value = pair.substring(equals + 1).trim();
                if (name.length() == 0) continue;
                webgateCookies.put(name, value);
            }
        }
        if (!webgateCookies.isEmpty()) {
            android.util.Log.i(TAG, "Native HTTP bridge storedCookies=" + webgateCookies.size());
        }
    }

    private static String readUtf8(InputStream input) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[16384];
        int read;
        while ((read = input.read(buffer)) != -1) {
            output.write(buffer, 0, read);
        }
        return output.toString("UTF-8");
    }

    private static String redactBodyPreview(String body) {
        String preview = body;
        preview = preview.replaceAll("(?i)(password[^=&<>]*[=\\\">]+)[^&<>\\\"]+", "$1[redacted]");
        preview = preview.replaceAll("(?i)(pass[^=&<>]*[=\\\">]+)[^&<>\\\"]+", "$1[redacted]");
        preview = preview.replaceAll("(?i)(email[^=&<>]*[=\\\">]+)[^&<>\\\"]+", "$1[redacted]");
        preview = preview.replaceAll("(?i)(account[^=&<>]*[=\\\">]+)[^&<>\\\"]+", "$1[redacted]");
        preview = preview.replaceAll("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[email]");
        preview = preview.replace('\n', ' ').replace('\r', ' ');
        if (preview.length() > 320) preview = preview.substring(0, 320) + "...";
        return preview;
    }

    private static String webgateXhrShim() {
        return "(function(){"
            + "if(window.__minimalusWebgateShim)return;"
            + "window.__minimalusWebgateShim=true;"
            + "var Native=window.MinimalusNative;"
            + "if(!Native||!Native.httpRequest)return;"
            + "var OriginalXHR=window.XMLHttpRequest;"
            + "function ShimXHR(){"
            + "this._xhr=new OriginalXHR();this._headers={};this._useNative=false;this.readyState=0;this.status=0;this.statusText='';this.responseText='';this.response='';this.onreadystatechange=null;this.onload=null;this.onerror=null;}"
            + "ShimXHR.prototype.open=function(method,url,async,user,password){"
            + "this._method=method||'GET';this._url=String(url);this._useNative=this._url.indexOf('https://webgate.ncplatform.net/')===0;"
            + "if(!this._useNative)return this._xhr.open.apply(this._xhr,arguments);this.readyState=1;this._emit('readystatechange');};"
            + "ShimXHR.prototype.setRequestHeader=function(k,v){if(this._useNative)this._headers[k]=v;else this._xhr.setRequestHeader(k,v);};"
            + "ShimXHR.prototype.getResponseHeader=function(k){return this._useNative?(k&&k.toLowerCase()==='content-type'?this._contentType:null):this._xhr.getResponseHeader(k);};"
            + "ShimXHR.prototype.getAllResponseHeaders=function(){return this._useNative?('content-type: '+(this._contentType||'text/xml')+'\\r\\n'):this._xhr.getAllResponseHeaders();};"
            + "ShimXHR.prototype.overrideMimeType=function(m){if(!this._useNative&&this._xhr.overrideMimeType)this._xhr.overrideMimeType(m);};"
            + "ShimXHR.prototype.abort=function(){if(!this._useNative)this._xhr.abort();};"
            + "function bodyToText(body){"
            + "if(!body)return '';"
            + "if(typeof body==='string')return body;"
            + "if(body instanceof ArrayBuffer)return new TextDecoder('utf-8').decode(new Uint8Array(body));"
            + "if(ArrayBuffer.isView(body))return new TextDecoder('utf-8').decode(body);"
            + "if(window.XMLSerializer&&body&&body.nodeType)return new XMLSerializer().serializeToString(body);"
            + "return String(body);"
            + "}"
            + "ShimXHR.prototype.send=function(body){"
            + "if(!this._useNative)return this._xhr.send(body);"
            + "try{var lines='';for(var k in this._headers)lines+=k+': '+this._headers[k]+'\\n';"
            + "var bodyText=bodyToText(body);var method=this._method||'GET';if(method.toUpperCase()==='GET'&&bodyText.length>0)method='POST';"
            + "console.log('[minimalus-webgate] native XHR '+method+' '+this._url+' bodyChars='+bodyText.length);"
            + "var result=Native.httpRequest(method,this._url,lines,bodyText);"
            + "var first=result.indexOf('\\n'),second=result.indexOf('\\n',first+1);"
            + "this.status=parseInt(result.slice(0,first),10)||599;this.statusText=this.status===200?'OK':'HTTP '+this.status;"
            + "this._contentType=result.slice(first+1,second);this.responseText=result.slice(second+1);this.response=this.responseText;"
            + "try{this.responseXML=(new DOMParser()).parseFromString(this.responseText,this._contentType&&this._contentType.indexOf('html')>=0?'text/html':'application/xml');}catch(parseError){this.responseXML=null;}"
            + "console.log('[minimalus-webgate] native XHR status '+this.status+' responseChars='+this.responseText.length);"
            + "this.readyState=4;this._emit('readystatechange');this._emit('load');this._emit('loadend');"
            + "}catch(e){this.status=599;this.statusText='Native bridge error';this.readyState=4;this.responseText=String(e);this.response=this.responseText;this._emit('readystatechange');this._emit('error');this._emit('loadend');}};"
            + "ShimXHR.prototype.addEventListener=function(type,fn){this['on'+type]=fn;};"
            + "ShimXHR.prototype.removeEventListener=function(type,fn){if(this['on'+type]===fn)this['on'+type]=null;};"
            + "ShimXHR.prototype._emit=function(type){var fn=this['on'+type];if(typeof fn==='function')fn.call(this,{type:type,target:this,currentTarget:this});};"
            + "['timeout','withCredentials','responseType'].forEach(function(prop){Object.defineProperty(ShimXHR.prototype,prop,{get:function(){return this._useNative?this['_'+prop]:this._xhr[prop];},set:function(v){if(this._useNative)this['_'+prop]=v;else this._xhr[prop]=v;}});});"
            + "ShimXHR.UNSENT=0;ShimXHR.OPENED=1;ShimXHR.HEADERS_RECEIVED=2;ShimXHR.LOADING=3;ShimXHR.DONE=4;"
            + "ShimXHR.prototype.UNSENT=0;ShimXHR.prototype.OPENED=1;ShimXHR.prototype.HEADERS_RECEIVED=2;ShimXHR.prototype.LOADING=3;ShimXHR.prototype.DONE=4;"
            + "window.XMLHttpRequest=ShimXHR;"
            + "console.log('[minimalus-webgate] XHR bridge installed');"
            + "})();";
    }
}
