package com.ty7.agent;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.app.DownloadManager;
import android.net.Uri;
import android.os.Environment;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.ActivityNotFoundException;
import android.widget.Toast;
import android.util.Log;

import com.getcapacitor.BridgeActivity;

import java.util.List;

public class MainActivity extends BridgeActivity {
    private static final String TAG = "7TY_Bank";
    private Context context;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(BankLauncherPlugin.class);
        registerPlugin(SMSReaderPlugin.class);
        super.onCreate(savedInstanceState);
        context = this;
        Log.d(TAG, "MainActivity created - v122 with SMS Reader");
        
        // Setup WebView sau khi bridge sẵn sàng
        new Handler(Looper.getMainLooper()).postDelayed(this::setupWebView, 300);
    }
    
    private void setupWebView() {
        try {
            WebView webView = getBridge().getWebView();
            if (webView == null) {
                Log.e(TAG, "WebView is null!");
                return;
            }
            
            // Transparent background
            webView.setBackgroundColor(android.graphics.Color.TRANSPARENT);
            webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);
            getWindow().getDecorView().setBackgroundColor(android.graphics.Color.TRANSPARENT);
            
            // Thêm JavaScript Interface để mở app
            webView.addJavascriptInterface(new AppLauncher(), "NativeAppLauncher");
            Log.d(TAG, "NativeAppLauncher interface added");
            
            // Override WebViewClient để xử lý VietQR deeplinks
            webView.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    String url = request.getUrl().toString();
                    Log.d(TAG, "shouldOverrideUrlLoading: " + url);
                    
                    // Xử lý VietQR deeplink
                    if (url.startsWith("https://dl.vietqr.io/") || 
                        url.startsWith("http://dl.vietqr.io/") ||
                        url.contains("vietqr.io/pay")) {
                        Log.d(TAG, "VietQR URL detected, opening in browser...");
                        try {
                            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            startActivity(intent);
                            return true; // Đã xử lý
                        } catch (Exception e) {
                            Log.e(TAG, "Error opening VietQR", e);
                        }
                    }
                    
                    // Xử lý các scheme đặc biệt (bank apps)
                    if (!url.startsWith("http://") && !url.startsWith("https://") && !url.startsWith("file://")) {
                        Log.d(TAG, "Custom scheme detected: " + url);
                        try {
                            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            startActivity(intent);
                            return true;
                        } catch (Exception e) {
                            Log.e(TAG, "Error opening custom scheme", e);
                        }
                    }
                    
                    // Để Capacitor xử lý các URL khác
                    return false;
                }
            });
            
            // Inject confirmation
            webView.post(() -> {
                webView.evaluateJavascript(
                    "window.NativeAppLauncherReady = true; console.log('NativeAppLauncher ready!');", 
                    null
                );
            });
            
            // Download listener
            webView.setDownloadListener((url, userAgent, contentDisposition, mimetype, contentLength) -> {
                Log.d(TAG, "Download: " + url);
                handleDownload(url, contentDisposition, mimetype);
            });
            
            Log.d(TAG, "WebView setup complete with custom WebViewClient");
            
        } catch (Exception e) {
            Log.e(TAG, "Error setting up WebView", e);
        }
    }
    
    // =============== JAVASCRIPT INTERFACE ===============
    public class AppLauncher {
        
        @JavascriptInterface
        public String openBankApp(String packageName) {
            Log.d(TAG, "openBankApp called: " + packageName);
            
            try {
                // Kiểm tra app đã cài chưa
                getPackageManager().getPackageInfo(packageName, 0);
                
                // Mở app
                Intent launchIntent = getPackageManager().getLaunchIntentForPackage(packageName);
                if (launchIntent != null) {
                    launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    startActivity(launchIntent);
                    
                    runOnUiThread(() -> Toast.makeText(context, "Đang mở app...", Toast.LENGTH_SHORT).show());
                    Log.d(TAG, "SUCCESS: App opened");
                    return "SUCCESS";
                } else {
                    Log.d(TAG, "FAILED: Launch intent is null");
                    return "FAILED";
                }
            } catch (PackageManager.NameNotFoundException e) {
                Log.d(TAG, "NOT_INSTALLED: " + packageName);
                runOnUiThread(() -> {
                    Toast.makeText(context, "App chưa cài đặt. Đang mở CH Play...", Toast.LENGTH_LONG).show();
                    openPlayStore(packageName);
                });
                return "NOT_INSTALLED";
            } catch (Exception e) {
                Log.e(TAG, "ERROR: " + e.getMessage());
                runOnUiThread(() -> Toast.makeText(context, "Lỗi: " + e.getMessage(), Toast.LENGTH_LONG).show());
                return "ERROR";
            }
        }
        
        @JavascriptInterface
        public String openDeeplink(String url) {
            Log.d(TAG, "openDeeplink called: " + url);
            
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                
                List<ResolveInfo> activities = getPackageManager().queryIntentActivities(intent, 0);
                if (activities.size() > 0) {
                    startActivity(intent);
                    Log.d(TAG, "SUCCESS: Deeplink opened, activities=" + activities.size());
                    return "SUCCESS";
                } else {
                    Log.d(TAG, "NO_HANDLER: No app can handle this URL");
                    return "NO_HANDLER";
                }
            } catch (Exception e) {
                Log.e(TAG, "ERROR: " + e.getMessage());
                return "ERROR";
            }
        }
        
        @JavascriptInterface
        public boolean isInstalled(String packageName) {
            try {
                getPackageManager().getPackageInfo(packageName, 0);
                return true;
            } catch (PackageManager.NameNotFoundException e) {
                return false;
            }
        }
        
        @JavascriptInterface
        public void toast(String message) {
            runOnUiThread(() -> Toast.makeText(context, message, Toast.LENGTH_SHORT).show());
        }
        
        private void openPlayStore(String packageName) {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + packageName));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
            } catch (ActivityNotFoundException e) {
                Intent intent = new Intent(Intent.ACTION_VIEW, 
                    Uri.parse("https://play.google.com/store/apps/details?id=" + packageName));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intent);
            }
        }
    }
    
    private void handleDownload(String url, String contentDisposition, String mimetype) {
        try {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.setMimeType(mimetype);
            
            String filename = "7ty-agent.apk";
            if (contentDisposition != null && contentDisposition.contains("filename=")) {
                int idx = contentDisposition.indexOf("filename=");
                filename = contentDisposition.substring(idx + 9).replace("\"", "").trim();
            }
            
            final String finalFilename = filename;
            
            request.setDescription("Đang tải " + filename);
            request.setTitle(filename);
            request.allowScanningByMediaScanner();
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
            
            DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            dm.enqueue(request);
            
            runOnUiThread(() -> Toast.makeText(context, "Đang tải " + finalFilename, Toast.LENGTH_LONG).show());
            
        } catch (Exception e) {
            Log.e(TAG, "Download error", e);
            try {
                Intent browserIntent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
                browserIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(browserIntent);
            } catch (Exception e2) {
                runOnUiThread(() -> Toast.makeText(context, "Lỗi tải file", Toast.LENGTH_SHORT).show());
            }
        }
    }
}
