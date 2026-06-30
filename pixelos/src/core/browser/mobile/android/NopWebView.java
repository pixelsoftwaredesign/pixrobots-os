package org.pixelos.nopbrowser;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.*;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * NOP Browser — Android WebView wrapper with Web3 resolution,
 * ad/tracker blocking, PixelOS wallet integration.
 *
 * Communication with the NOP Python bridge happens via local HTTP
 * on a configurable port (default 9876).
 *
 * Build: ./gradlew assembleRelease
 */
public class NopWebView extends AppCompatActivity {

    private WebView webView;
    private EditText urlBar;
    private ImageButton btnBack, btnForward, btnRefresh, btnBookmark, btnMenu;
    private ProgressBar progressBar;
    private TextView badgeWeb3;
    private LinearLayout tabBar;
    private String currentUrl = "";
    private static final String NOP_BRIDGE = "http://127.0.0.1:9876";
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        urlBar = findViewById(R.id.url_bar);
        btnBack = findViewById(R.id.btn_back);
        btnForward = findViewById(R.id.btn_forward);
        btnRefresh = findViewById(R.id.btn_refresh);
        btnBookmark = findViewById(R.id.btn_bookmark);
        btnMenu = findViewById(R.id.btn_menu);
        progressBar = findViewById(R.id.progress_bar);
        badgeWeb3 = findViewById(R.id.badge_web3);
        tabBar = findViewById(R.id.tab_bar);

        setupWebView();
        setupNavigation();
        injectBridgeJS();
        loadUrl("https://duckduckgo.com");
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setUserAgentString(
            "Mozilla/5.0 (Linux; Android " + android.os.Build.VERSION.RELEASE +
            "; PixelOS-NOP/1.0) AppleWebKit/537.36"
        );

        // Ad-blocking via WebViewClient.shouldInterceptRequest
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                view.loadUrl(request.getUrl().toString());
                return true;
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                try {
                    String encUrl = URLEncoder.encode(url, "UTF-8");
                    HttpURLConnection conn = (HttpURLConnection)
                        new URL(NOP_BRIDGE + "/check_url?url=" + encUrl).openConnection();
                    conn.setConnectTimeout(2000);
                    conn.setReadTimeout(2000);
                    BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder resp = new StringBuilder();
                    String line;
                    while ((line = rd.readLine()) != null) resp.append(line);
                    rd.close();

                    JSONObject json = new JSONObject(resp.toString());
                    if (json.optBoolean("blocked", false)) {
                        return new WebResourceResponse("text/plain", "utf-8", null);
                    }
                } catch (Exception ignored) {}
                return null;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                currentUrl = url;
                urlBar.setText(url);
                progressBar.setVisibility(View.VISIBLE);
                checkWeb3(url);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                webView.evaluateJavascript(
                    "javascript:(function(){ " +
                    "  if(window.NOPBridgeReady) return; " +
                    "  window.NOPBridgeReady = true; " +
                    "  console.log('[NOP] Bridge ready'); " +
                    "})()", null);
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }
        });
    }

    private void setupNavigation() {
        urlBar.setOnKeyListener((v, keyCode, event) -> {
            if (keyCode == KeyEvent.KEYCODE_ENTER && event.getAction() == KeyEvent.ACTION_DOWN) {
                loadUrl(urlBar.getText().toString());
                return true;
            }
            return false;
        });

        btnBack.setOnClickListener(v -> { if (webView.canGoBack()) webView.goBack(); });
        btnForward.setOnClickListener(v -> { if (webView.canGoForward()) webView.goForward(); });
        btnRefresh.setOnClickListener(v -> webView.reload());

        btnBookmark.setOnClickListener(v -> {
            android.content.SharedPreferences prefs = getSharedPreferences("nop_bookmarks", MODE_PRIVATE);
            String bookmarks = prefs.getString("bookmarks", "[]");
            try {
                org.json.JSONArray arr = new org.json.JSONArray(bookmarks);
                JSONObject bm = new JSONObject();
                bm.put("url", currentUrl);
                bm.put("title", webView.getTitle());
                arr.put(bm);
                prefs.edit().putString("bookmarks", arr.toString()).apply();
                Toast.makeText(this, "Favori ajouté", Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, "Erreur favori", Toast.LENGTH_SHORT).show();
            }
        });

        btnMenu.setOnClickListener(v -> showMenu());
    }

    private void loadUrl(String input) {
        String url = input.trim();
        if (url.isEmpty()) return;

        // Web3 resolution via bridge
        if (url.contains(".eth") || url.contains(".pixel") || url.contains(".pxl") ||
            url.contains(".ipfs") || url.contains(".bit") || url.contains(".crypto")) {
            resolveWeb3(url);
            return;
        }

        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            if (url.contains(".")) url = "https://" + url;
            else url = "https://duckduckgo.com/?q=" + Uri.encode(url);
        }

        webView.loadUrl(url);
    }

    private void resolveWeb3(String url) {
        executor.execute(() -> {
            try {
                String encUrl = URLEncoder.encode(url, "UTF-8");
                HttpURLConnection conn = (HttpURLConnection)
                    new URL(NOP_BRIDGE + "/resolve?url=" + encUrl).openConnection();
                conn.setConnectTimeout(5000);
                BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = rd.readLine()) != null) resp.append(line);
                rd.close();

                JSONObject json = new JSONObject(resp.toString());
                String resolved = json.optString("resolved_url", url);
                String web3Type = json.optString("web3_type", "standard");

                mainHandler.post(() -> {
                    updateWeb3Badge(web3Type, json);
                    webView.loadUrl(resolved);
                });
            } catch (Exception e) {
                mainHandler.post(() -> webView.loadUrl(url));
            }
        });
    }

    private void checkWeb3(String url) {
        executor.execute(() -> {
            try {
                String encUrl = URLEncoder.encode(url, "UTF-8");
                HttpURLConnection conn = (HttpURLConnection)
                    new URL(NOP_BRIDGE + "/resolve?url=" + encUrl).openConnection();
                conn.setConnectTimeout(3000);
                BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = rd.readLine()) != null) resp.append(line);
                rd.close();

                JSONObject json = new JSONObject(resp.toString());
                String web3Type = json.optString("web3_type", "standard");
                if (!web3Type.equals("standard")) {
                    mainHandler.post(() -> updateWeb3Badge(web3Type, json));
                }
            } catch (Exception ignored) {}
        });
    }

    private void updateWeb3Badge(String type, JSONObject info) {
        String label;
        int color;
        switch (type) {
            case "ens":      label = "⬡ ENS";    color = 0xFFE94560; break;
            case "pixel":    label = "⬡ .pixel"; color = 0xFFE94560; break;
            case "ipfs":     label = "⬡ IPFS";   color = 0xFFE94560; break;
            case "bit":      label = "⬡ .bit";   color = 0xFFE94560; break;
            case "pixelos":  label = "⬡ PixelOS"; color = 0xFFE94560; break;
            default:         label = "🌐";        color = 0xFF0F3460; break;
        }
        badgeWeb3.setText(label);
        badgeWeb3.setBackgroundColor(color);
    }

    private void injectBridgeJS() {
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                String js = "javascript:(function(){" +
                    "if(window.__nop_injected)return;window.__nop_injected=true;" +
                    "window.NOP={resolve:u=>fetch('"+NOP_BRIDGE+"/resolve?url='+encodeURIComponent(u)).then(r=>r.json())," +
                    "checkUrl:u=>fetch('"+NOP_BRIDGE+"/check_url?url='+encodeURIComponent(u)).then(r=>r.json())," +
                    "walletStatus:()=>fetch('"+NOP_BRIDGE+"/wallet/status').then(r=>r.json())," +
                    "walletBalance:a=>fetch('"+NOP_BRIDGE+"/wallet/balance'+(a?'?address='+a:'')).then(r=>r.json())," +
                    "signTx:t=>fetch('"+NOP_BRIDGE+"/sign_tx',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(t)}).then(r=>r.json())" +
                    "};console.log('[NOP] Bridge OK')})()";
                webView.evaluateJavascript(js, null);
            }
        });
    }

    private void showMenu() {
        String[] items = {"Favoris", "Historique", "Paramètres", "Clear Cache", "Wallet"};
        new AlertDialog.Builder(this)
            .setTitle("NOP Menu")
            .setItems(items, (dialog, which) -> {
                switch (which) {
                    case 0: showBookmarks(); break;
                    case 1: showHistory(); break;
                    case 2: showSettings(); break;
                    case 3: clearCache(); break;
                    case 4: showWallet(); break;
                }
            }).show();
    }

    private void showBookmarks() {
        android.content.SharedPreferences prefs = getSharedPreferences("nop_bookmarks", MODE_PRIVATE);
        String bookmarks = prefs.getString("bookmarks", "[]");
        try {
            org.json.JSONArray arr = new org.json.JSONArray(bookmarks);
            String[] urls = new String[arr.length()];
            for (int i = 0; i < arr.length(); i++) {
                urls[i] = arr.getJSONObject(i).optString("url", "");
            }
            new AlertDialog.Builder(this)
                .setTitle("Favoris")
                .setItems(urls, (d, i) -> webView.loadUrl(urls[i]))
                .show();
        } catch (Exception ignored) {}
    }

    private void showHistory() {
        // History stored via SharedPreferences for simplicity
        android.content.SharedPreferences prefs = getSharedPreferences("nop_history", MODE_PRIVATE);
        String history = prefs.getString("history", "[]");
        try {
            org.json.JSONArray arr = new org.json.JSONArray(history);
            String[] urls = new String[arr.length() > 20 ? 20 : arr.length()];
            for (int i = 0; i < urls.length; i++) {
                urls[i] = arr.getJSONObject(arr.length() - 1 - i).optString("url", "");
            }
            new AlertDialog.Builder(this)
                .setTitle("Historique")
                .setItems(urls, (d, i) -> webView.loadUrl(urls[i]))
                .show();
        } catch (Exception ignored) {}
    }

    private void showSettings() {
        final EditText input = new EditText(this);
        input.setHint("Page d'accueil");
        new AlertDialog.Builder(this)
            .setTitle("Paramètres")
            .setView(input)
            .setPositiveButton("OK", (d, i) -> {
                String url = input.getText().toString().trim();
                if (!url.isEmpty()) webView.loadUrl(url);
            })
            .setNegativeButton("Annuler", null)
            .show();
    }

    private void clearCache() {
        webView.clearCache(true);
        webView.clearHistory();
        Toast.makeText(this, "Cache effacé", Toast.LENGTH_SHORT).show();
        executor.execute(() -> {
            try {
                HttpURLConnection conn = (HttpURLConnection)
                    new URL(NOP_BRIDGE + "/clear_cache").openConnection();
                conn.setRequestMethod("POST");
                conn.connect();
            } catch (Exception ignored) {}
        });
    }

    private void showWallet() {
        executor.execute(() -> {
            try {
                HttpURLConnection conn = (HttpURLConnection)
                    new URL(NOP_BRIDGE + "/wallet/status").openConnection();
                conn.setConnectTimeout(3000);
                BufferedReader rd = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = rd.readLine()) != null) resp.append(line);
                rd.close();

                JSONObject json = new JSONObject(resp.toString());
                boolean available = json.optBoolean("available", false);
                mainHandler.post(() -> {
                    new AlertDialog.Builder(this)
                        .setTitle("Wallet PixelOS")
                        .setMessage(available ? "✅ Wallet connecté" : "❌ Wallet non disponible")
                        .setPositiveButton("OK", null)
                        .show();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    new AlertDialog.Builder(this)
                        .setTitle("Wallet PixelOS")
                        .setMessage("❌ Wallet non disponible")
                        .setPositiveButton("OK", null)
                        .show();
                });
            }
        });
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
