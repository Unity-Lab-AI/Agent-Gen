package ai.unitylab.u3e;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

/**
 * U3E — a WebView onto the orb running on your own machine.
 *
 * VENDORED PATTERN, not imported: the shape of this wrapper comes from the
 * sibling "Ollama 18+ local Unity" project, whose APK is built and working.
 * Copied 2026-08-29. That project versions its original independently.
 *
 * WHAT IS DIFFERENT HERE, AND WHY
 *   The sibling needed exactly one permission: INTERNET. U3E's orb LISTENS and
 *   can SEE, so this build additionally needs RECORD_AUDIO and CAMERA — and a
 *   WebView does NOT forward getUserMedia to the page unless
 *   onPermissionRequest explicitly grants it. Without that override the mic and
 *   camera fail silently inside the page, which looks like a bug in the app
 *   rather than a missing hook here.
 */
public class MainActivity extends ComponentActivity {

    private static final String PREFS = "u3e";
    private static final String KEY_URL = "server_url";
    private static final int REQ_PERMS = 1001;

    private WebView web;
    private String serverUrl;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        SharedPreferences p = getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        serverUrl = p.getString(KEY_URL, null);

        askForPermissions();

        if (serverUrl == null || serverUrl.isEmpty()) {
            showSetup();
        } else {
            showWeb(serverUrl);
        }
    }

    /**
     * Runtime permissions. Both are REFUSABLE and the app still works — the orb
     * runs typed, and it says what is missing rather than looping on a prompt.
     */
    private void askForPermissions() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return;
        String[] want = { Manifest.permission.RECORD_AUDIO, Manifest.permission.CAMERA };
        boolean need = false;
        for (String w : want) {
            if (ContextCompat.checkSelfPermission(this, w) != PackageManager.PERMISSION_GRANTED) need = true;
        }
        if (need) ActivityCompat.requestPermissions(this, want, REQ_PERMS);
    }

    /** A setup screen, not a hardcoded address — the machine's IP is yours. */
    private void showSetup() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(48, 96, 48, 48);
        root.setBackgroundColor(0xFF0E0E11);

        TextView title = new TextView(this);
        title.setText("Unity");
        title.setTextSize(22);
        title.setTextColor(0xFFE6E4EA);
        root.addView(title);

        TextView hint = new TextView(this);
        hint.setText("Address of the machine running `node serve/server.mjs --host 0.0.0.0`.\n"
                + "The server prints it on start.");
        hint.setTextSize(13);
        hint.setTextColor(0xFF8B8896);
        hint.setPadding(0, 24, 0, 24);
        root.addView(hint);

        final EditText input = new EditText(this);
        input.setHint("http://192.168.1.10:8790");
        input.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        input.setTextColor(0xFFE6E4EA);
        input.setHintTextColor(0xFF6B6876);
        root.addView(input);

        Button go = new Button(this);
        go.setText("Connect");
        go.setOnClickListener(v -> {
            String url = input.getText().toString().trim();
            if (url.isEmpty()) { toast("Enter the address the server printed"); return; }
            if (!url.startsWith("http://") && !url.startsWith("https://")) url = "http://" + url;
            getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_URL, url).apply();
            serverUrl = url;
            showWeb(url);
        });
        root.addView(go, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        setContentView(root);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void showWeb(String url) {
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);          // the transcript and gallery live in localStorage
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);

        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient() {
            /**
             * ⛔ THE HOOK WITHOUT WHICH THE MIC AND CAMERA FAIL SILENTLY.
             * A WebView denies getUserMedia by default even when the app itself
             * holds the OS permission. The page would show "permission refused"
             * and nothing in logcat would explain why.
             */
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
        });

        web.setBackgroundColor(0xFF0E0E11);
        setContentView(web);
        web.loadUrl(url);
    }

    @Override
    public void onRequestPermissionsResult(int code, @NonNull String[] perms, @NonNull int[] results) {
        super.onRequestPermissionsResult(code, perms, results);
        if (code != REQ_PERMS) return;
        for (int i = 0; i < perms.length; i++) {
            if (results[i] != PackageManager.PERMISSION_GRANTED) {
                // Refusal is an answer. The orb still works typed; it will say
                // what is unavailable rather than pretending or re-prompting.
                toast(perms[i].endsWith("CAMERA")
                        ? "Camera refused — she cannot be shown things. Everything else works."
                        : "Microphone refused — talking is off. Everything else works.");
            }
        }
    }

    /** Long-press anywhere on the setup screen is not a thing; use app data reset. */
    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack();
        else super.onBackPressed();
    }

    private void toast(String m) { Toast.makeText(this, m, Toast.LENGTH_LONG).show(); }
}
