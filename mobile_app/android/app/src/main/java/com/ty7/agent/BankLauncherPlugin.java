package com.ty7.agent;

import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.net.Uri;
import android.widget.Toast;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.List;

@CapacitorPlugin(name = "BankLauncher")
public class BankLauncherPlugin extends Plugin {
    private static final String TAG = "BankLauncher";

    // Mở app bằng package name
    @PluginMethod
    public void openApp(PluginCall call) {
        String packageName = call.getString("packageName");
        Log.d(TAG, "openApp: " + packageName);
        
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Package name is required");
            return;
        }
        
        try {
            Intent launchIntent = getActivity().getPackageManager().getLaunchIntentForPackage(packageName);
            if (launchIntent != null) {
                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getActivity().startActivity(launchIntent);
                
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("method", "package");
                call.resolve(ret);
            } else {
                JSObject ret = new JSObject();
                ret.put("success", false);
                ret.put("error", "App not installed");
                call.resolve(ret);
            }
        } catch (Exception e) {
            Log.e(TAG, "openApp error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // Mở deeplink URL (cho VietQR, bank transfer links)
    @PluginMethod
    public void openUrl(PluginCall call) {
        String url = call.getString("url");
        Log.d(TAG, "openUrl: " + url);
        
        if (url == null || url.isEmpty()) {
            call.reject("URL is required");
            return;
        }
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            
            // Kiểm tra có app nào handle được URL này không
            List<ResolveInfo> activities = getActivity().getPackageManager()
                .queryIntentActivities(intent, 0);
            
            if (activities.size() > 0) {
                getActivity().startActivity(intent);
                Log.d(TAG, "openUrl success, activities: " + activities.size());
                
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("activitiesCount", activities.size());
                call.resolve(ret);
            } else {
                Log.d(TAG, "openUrl: No app can handle this URL");
                JSObject ret = new JSObject();
                ret.put("success", false);
                ret.put("error", "No app can handle this URL");
                call.resolve(ret);
            }
        } catch (Exception e) {
            Log.e(TAG, "openUrl error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // Mở VietQR deeplink
    @PluginMethod
    public void openVietQR(PluginCall call) {
        String bankCode = call.getString("bankCode", "");
        String accountNo = call.getString("accountNo", "");
        String amount = call.getString("amount", "0");
        String content = call.getString("content", "");
        String accountName = call.getString("accountName", "");
        
        Log.d(TAG, "openVietQR: bank=" + bankCode + ", account=" + accountNo + ", amount=" + amount);
        
        // Tạo VietQR deeplink URL
        String vietqrUrl = "https://dl.vietqr.io/pay?app=" + bankCode + 
                          "&ba=" + bankCode + "-" + accountNo + 
                          "&am=" + amount + 
                          "&tn=" + Uri.encode(content);
        
        Log.d(TAG, "VietQR URL: " + vietqrUrl);
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(vietqrUrl));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getActivity().startActivity(intent);
            
            JSObject ret = new JSObject();
            ret.put("success", true);
            ret.put("url", vietqrUrl);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "openVietQR error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // Kiểm tra app đã cài chưa
    @PluginMethod
    public void isInstalled(PluginCall call) {
        String packageName = call.getString("packageName");
        
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Package name is required");
            return;
        }
        
        boolean installed = false;
        try {
            getActivity().getPackageManager().getPackageInfo(packageName, 0);
            installed = true;
        } catch (PackageManager.NameNotFoundException e) {
            installed = false;
        }
        
        Log.d(TAG, "isInstalled: " + packageName + " = " + installed);
        
        JSObject ret = new JSObject();
        ret.put("installed", installed);
        call.resolve(ret);
    }
    
    // Mở Play Store
    @PluginMethod
    public void openPlayStore(PluginCall call) {
        String packageName = call.getString("packageName");
        
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Package name is required");
            return;
        }
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + packageName));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getActivity().startActivity(intent);
            
            JSObject ret = new JSObject();
            ret.put("success", true);
            call.resolve(ret);
        } catch (Exception e) {
            try {
                Intent intent = new Intent(Intent.ACTION_VIEW, 
                    Uri.parse("https://play.google.com/store/apps/details?id=" + packageName));
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getActivity().startActivity(intent);
                
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("method", "web");
                call.resolve(ret);
            } catch (Exception e2) {
                call.reject("Error: " + e2.getMessage());
            }
        }
    }
    
    // Hiển thị toast
    @PluginMethod
    public void showToast(PluginCall call) {
        String message = call.getString("message", "");
        
        getActivity().runOnUiThread(() -> {
            Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
        });
        
        JSObject ret = new JSObject();
        ret.put("success", true);
        call.resolve(ret);
    }
    
    // Mở URL trong Chrome (external browser)
    @PluginMethod
    public void openInChrome(PluginCall call) {
        String url = call.getString("url");
        Log.d(TAG, "openInChrome: " + url);
        
        if (url == null || url.isEmpty()) {
            call.reject("URL is required");
            return;
        }
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            
            // Thử mở với Chrome trước
            intent.setPackage("com.android.chrome");
            
            try {
                getActivity().startActivity(intent);
                Log.d(TAG, "Opened in Chrome");
                
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("browser", "chrome");
                call.resolve(ret);
            } catch (Exception chromeError) {
                // Chrome không có, thử trình duyệt mặc định
                Log.d(TAG, "Chrome not found, trying default browser");
                intent.setPackage(null);
                
                // Thêm CATEGORY_BROWSABLE để đảm bảo mở trong browser
                intent.addCategory(Intent.CATEGORY_BROWSABLE);
                
                getActivity().startActivity(intent);
                
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("browser", "default");
                call.resolve(ret);
            }
        } catch (Exception e) {
            Log.e(TAG, "openInChrome error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // Mở URL với Intent Chooser (để user chọn app)
    @PluginMethod
    public void openWithChooser(PluginCall call) {
        String url = call.getString("url");
        Log.d(TAG, "openWithChooser: " + url);
        
        if (url == null || url.isEmpty()) {
            call.reject("URL is required");
            return;
        }
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            Intent chooser = Intent.createChooser(intent, "Mở với...");
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getActivity().startActivity(chooser);
            
            JSObject ret = new JSObject();
            ret.put("success", true);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "openWithChooser error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // v112: Mở app ngân hàng với deeplink chuyển khoản (giống Zalo)
    // Thử nhiều phương pháp: scheme deeplink, intent URL, package launch
    @PluginMethod
    public void openBankTransfer(PluginCall call) {
        String packageName = call.getString("packageName");
        String scheme = call.getString("scheme");
        String accountNo = call.getString("accountNo");
        String bankBin = call.getString("bankBin");
        String amount = call.getString("amount", "0");
        String content = call.getString("content", "");
        
        Log.d(TAG, "openBankTransfer: package=" + packageName + ", scheme=" + scheme);
        Log.d(TAG, "Transfer info: account=" + accountNo + ", bankBin=" + bankBin + ", amount=" + amount);
        
        if (packageName == null || packageName.isEmpty()) {
            call.reject("Package name is required");
            return;
        }
        
        try {
            // Kiểm tra app đã cài chưa
            boolean appInstalled = false;
            try {
                getActivity().getPackageManager().getPackageInfo(packageName, 0);
                appInstalled = true;
            } catch (PackageManager.NameNotFoundException e) {
                appInstalled = false;
            }
            
            if (!appInstalled) {
                JSObject ret = new JSObject();
                ret.put("success", false);
                ret.put("error", "App not installed");
                ret.put("packageName", packageName);
                call.resolve(ret);
                return;
            }
            
            boolean opened = false;
            String method = "";
            
            // PHƯƠNG PHÁP 1: Deeplink trực tiếp với scheme của ngân hàng
            if (scheme != null && !scheme.isEmpty() && !opened) {
                try {
                    // Tạo deeplink URL theo format của từng ngân hàng
                    String deeplink = buildBankDeeplink(scheme, packageName, accountNo, bankBin, amount, content);
                    Log.d(TAG, "Trying deeplink: " + deeplink);
                    
                    Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(deeplink));
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    intent.setPackage(packageName);
                    
                    List<ResolveInfo> activities = getActivity().getPackageManager()
                        .queryIntentActivities(intent, 0);
                    
                    if (activities.size() > 0) {
                        getActivity().startActivity(intent);
                        opened = true;
                        method = "deeplink";
                        Log.d(TAG, "SUCCESS: Opened via deeplink");
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Deeplink failed: " + e.getMessage());
                }
            }
            
            // PHƯƠNG PHÁP 2: Intent URL (Android Intent scheme)
            if (!opened && scheme != null && !scheme.isEmpty()) {
                try {
                    String intentUrl = "intent://transfer?bankCode=" + bankBin + 
                                      "&accountNo=" + accountNo + 
                                      "&amount=" + amount + 
                                      "&content=" + Uri.encode(content) + 
                                      "#Intent;scheme=" + scheme + 
                                      ";package=" + packageName + 
                                      ";end";
                    Log.d(TAG, "Trying Intent URL: " + intentUrl);
                    
                    Intent intent = Intent.parseUri(intentUrl, Intent.URI_INTENT_SCHEME);
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    
                    List<ResolveInfo> activities = getActivity().getPackageManager()
                        .queryIntentActivities(intent, 0);
                    
                    if (activities.size() > 0) {
                        getActivity().startActivity(intent);
                        opened = true;
                        method = "intent_url";
                        Log.d(TAG, "SUCCESS: Opened via Intent URL");
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Intent URL failed: " + e.getMessage());
                }
            }
            
            // PHƯƠNG PHÁP 3: Mở app và để clipboard chứa thông tin
            if (!opened) {
                try {
                    Intent launchIntent = getActivity().getPackageManager().getLaunchIntentForPackage(packageName);
                    if (launchIntent != null) {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        
                        // Copy nội dung vào clipboard
                        android.content.ClipboardManager clipboard = (android.content.ClipboardManager) 
                            getActivity().getSystemService(android.content.Context.CLIPBOARD_SERVICE);
                        android.content.ClipData clip = android.content.ClipData.newPlainText("transfer", content);
                        clipboard.setPrimaryClip(clip);
                        
                        getActivity().startActivity(launchIntent);
                        opened = true;
                        method = "package_launch";
                        Log.d(TAG, "SUCCESS: Opened via package launch");
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Package launch failed: " + e.getMessage());
                }
            }
            
            JSObject ret = new JSObject();
            ret.put("success", opened);
            ret.put("method", method);
            ret.put("packageName", packageName);
            call.resolve(ret);
            
        } catch (Exception e) {
            Log.e(TAG, "openBankTransfer error", e);
            call.reject("Error: " + e.getMessage());
        }
    }
    
    // Xây dựng deeplink cho từng ngân hàng - Danh sách đầy đủ
    private String buildBankDeeplink(String scheme, String packageName, String accountNo, String bankBin, String amount, String content) {
        String encodedContent = Uri.encode(content);
        
        // MB Bank
        if (scheme.equals("mbbank") || packageName.equals("com.mbmobile")) {
            return "mbbank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // Vietcombank
        else if (scheme.equals("vcb") || packageName.equals("com.VCB")) {
            return "vcbdigibank://transfer?bankCode=" + bankBin + "&account=" + accountNo + "&amount=" + amount + "&memo=" + encodedContent;
        }
        // Techcombank
        else if (scheme.equals("techcombank") || packageName.equals("vn.com.techcombank.bb.app")) {
            return "techcombank://transfer?bankBin=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // BIDV
        else if (scheme.equals("bidv") || packageName.equals("com.vnpay.bidv")) {
            return "bidvsmartbanking://transfer?bankId=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // VPBank
        else if (scheme.equals("vpbank") || packageName.equals("com.vnpay.vpbankonline")) {
            return "vpbank://transfer?toBank=" + bankBin + "&toAccount=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // TPBank
        else if (scheme.equals("tpbank") || packageName.equals("com.tpb.mb.gprsandroid")) {
            return "tpb://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&description=" + encodedContent;
        }
        // Vietinbank
        else if (scheme.equals("vietinbank") || packageName.equals("com.vietinbank.ipay")) {
            return "vietinbank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // ACB
        else if (scheme.equals("acb") || packageName.equals("mobile.acb.com.vn")) {
            return "acbone://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&memo=" + encodedContent;
        }
        // Sacombank
        else if (scheme.equals("sacombank") || packageName.equals("com.sacombank.smbhome")) {
            return "sacombank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // SHB
        else if (scheme.equals("shb") || packageName.equals("vn.shb.mbanking")) {
            return "shbmobile://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // HDBank
        else if (scheme.equals("hdbank") || packageName.equals("com.vnpay.hdbank")) {
            return "hdbank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // OCB
        else if (scheme.equals("ocb") || packageName.equals("com.ocb.ombmobile")) {
            return "ocbomni://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // MSB
        else if (scheme.equals("msb") || packageName.equals("com.vnpay.msb")) {
            return "msb://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // VIB
        else if (scheme.equals("vib") || packageName.equals("com.vib.myvib2")) {
            return "myvib://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // Agribank
        else if (scheme.equals("agribank") || packageName.equals("com.vnpay.agribank")) {
            return "agribank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // SeABank
        else if (packageName.equals("vn.com.seabank.mb")) {
            return "seabank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // LPBank (LienViet)
        else if (packageName.equals("com.lpbank.mobilebanking")) {
            return "lpbank://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
        // Mặc định: dùng scheme chung
        else {
            return scheme + "://transfer?bankCode=" + bankBin + "&accountNo=" + accountNo + "&amount=" + amount + "&content=" + encodedContent;
        }
    }
    
    // v116: Tải ảnh QR từ URL, lưu vào gallery, rồi mở app ngân hàng
    @PluginMethod
    public void saveQRAndOpenApp(PluginCall call) {
        String imageUrl = call.getString("imageUrl");
        String packageName = call.getString("packageName");
        String fileName = call.getString("fileName", "VietQR_" + System.currentTimeMillis() + ".png");
        
        Log.d(TAG, "saveQRAndOpenApp: url=" + imageUrl + ", package=" + packageName);
        
        if (imageUrl == null || imageUrl.isEmpty()) {
            call.reject("Image URL is required");
            return;
        }
        
        // Chạy trên background thread
        new Thread(() -> {
            try {
                // 1. Tải ảnh từ URL
                java.net.URL url = new java.net.URL(imageUrl);
                java.net.HttpURLConnection connection = (java.net.HttpURLConnection) url.openConnection();
                connection.setDoInput(true);
                connection.connect();
                java.io.InputStream input = connection.getInputStream();
                android.graphics.Bitmap bitmap = android.graphics.BitmapFactory.decodeStream(input);
                
                if (bitmap == null) {
                    getActivity().runOnUiThread(() -> {
                        JSObject ret = new JSObject();
                        ret.put("success", false);
                        ret.put("error", "Failed to download image");
                        call.resolve(ret);
                    });
                    return;
                }
                
                // 2. Lưu vào MediaStore (Gallery)
                String savedPath = "";
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                    // Android 10+
                    android.content.ContentValues values = new android.content.ContentValues();
                    values.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, fileName);
                    values.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/png");
                    values.put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, android.os.Environment.DIRECTORY_PICTURES + "/VietQR");
                    
                    android.net.Uri uri = getActivity().getContentResolver().insert(
                        android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                    
                    if (uri != null) {
                        java.io.OutputStream out = getActivity().getContentResolver().openOutputStream(uri);
                        bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
                        out.close();
                        savedPath = uri.toString();
                    }
                } else {
                    // Android 9 và cũ hơn
                    java.io.File dir = new java.io.File(android.os.Environment.getExternalStoragePublicDirectory(
                        android.os.Environment.DIRECTORY_PICTURES), "VietQR");
                    if (!dir.exists()) dir.mkdirs();
                    
                    java.io.File file = new java.io.File(dir, fileName);
                    java.io.FileOutputStream out = new java.io.FileOutputStream(file);
                    bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
                    out.close();
                    
                    // Notify gallery
                    Intent scanIntent = new Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE);
                    scanIntent.setData(android.net.Uri.fromFile(file));
                    getActivity().sendBroadcast(scanIntent);
                    
                    savedPath = file.getAbsolutePath();
                }
                
                Log.d(TAG, "QR saved to: " + savedPath);
                
                // 3. Mở app ngân hàng
                boolean appOpened = false;
                if (packageName != null && !packageName.isEmpty()) {
                    Intent launchIntent = getActivity().getPackageManager().getLaunchIntentForPackage(packageName);
                    if (launchIntent != null) {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        getActivity().startActivity(launchIntent);
                        appOpened = true;
                    }
                }
                
                final String finalPath = savedPath;
                final boolean finalAppOpened = appOpened;
                
                getActivity().runOnUiThread(() -> {
                    JSObject ret = new JSObject();
                    ret.put("success", true);
                    ret.put("savedPath", finalPath);
                    ret.put("appOpened", finalAppOpened);
                    call.resolve(ret);
                });
                
            } catch (Exception e) {
                Log.e(TAG, "saveQRAndOpenApp error", e);
                getActivity().runOnUiThread(() -> {
                    JSObject ret = new JSObject();
                    ret.put("success", false);
                    ret.put("error", e.getMessage());
                    call.resolve(ret);
                });
            }
        }).start();
    }
    
    // v117: Share ảnh QR trực tiếp vào app ngân hàng - nhanh nhất!
    @PluginMethod
    public void shareQRToBank(PluginCall call) {
        String imageUrl = call.getString("imageUrl");
        String packageName = call.getString("packageName");
        String fileName = call.getString("fileName", "VietQR_" + System.currentTimeMillis() + ".png");
        
        Log.d(TAG, "shareQRToBank: url=" + imageUrl + ", package=" + packageName);
        
        if (imageUrl == null || imageUrl.isEmpty()) {
            call.reject("Image URL is required");
            return;
        }
        
        new Thread(() -> {
            try {
                // 1. Tải ảnh
                java.net.URL url = new java.net.URL(imageUrl);
                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
                conn.setDoInput(true);
                conn.connect();
                android.graphics.Bitmap bitmap = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());
                
                if (bitmap == null) {
                    getActivity().runOnUiThread(() -> {
                        JSObject ret = new JSObject();
                        ret.put("success", false);
                        ret.put("error", "Download failed");
                        call.resolve(ret);
                    });
                    return;
                }
                
                // 2. Lưu vào cache để share
                java.io.File cacheDir = new java.io.File(getActivity().getCacheDir(), "qr_share");
                if (!cacheDir.exists()) cacheDir.mkdirs();
                java.io.File imageFile = new java.io.File(cacheDir, fileName);
                java.io.FileOutputStream out = new java.io.FileOutputStream(imageFile);
                bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
                out.close();
                
                // 3. Tạo content URI
                android.net.Uri imageUri = androidx.core.content.FileProvider.getUriForFile(
                    getActivity(),
                    getActivity().getPackageName() + ".fileprovider",
                    imageFile
                );
                
                getActivity().runOnUiThread(() -> {
                    try {
                        // 4. Tạo Share Intent
                        Intent shareIntent = new Intent(Intent.ACTION_SEND);
                        shareIntent.setType("image/png");
                        shareIntent.putExtra(Intent.EXTRA_STREAM, imageUri);
                        shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        
                        // Nếu có package name, share trực tiếp vào app đó
                        if (packageName != null && !packageName.isEmpty()) {
                            shareIntent.setPackage(packageName);
                            
                            try {
                                getActivity().startActivity(shareIntent);
                                
                                JSObject ret = new JSObject();
                                ret.put("success", true);
                                ret.put("method", "direct_share");
                                ret.put("packageName", packageName);
                                call.resolve(ret);
                                return;
                            } catch (android.content.ActivityNotFoundException e) {
                                Log.d(TAG, "Direct share failed, trying chooser");
                            }
                        }
                        
                        // Fallback: mở chooser
                        Intent chooser = Intent.createChooser(shareIntent, "Chia sẻ QR đến ngân hàng");
                        getActivity().startActivity(chooser);
                        
                        JSObject ret = new JSObject();
                        ret.put("success", true);
                        ret.put("method", "chooser");
                        call.resolve(ret);
                        
                    } catch (Exception e) {
                        Log.e(TAG, "Share error", e);
                        JSObject ret = new JSObject();
                        ret.put("success", false);
                        ret.put("error", e.getMessage());
                        call.resolve(ret);
                    }
                });
                
            } catch (Exception e) {
                Log.e(TAG, "shareQRToBank error", e);
                getActivity().runOnUiThread(() -> {
                    JSObject ret = new JSObject();
                    ret.put("success", false);
                    ret.put("error", e.getMessage());
                    call.resolve(ret);
                });
            }
        }).start();
    }
    
    // v118: Lưu QR và mở bằng ACTION_VIEW - để bank app tự đọc
    @PluginMethod
    public void openQRInBankApp(PluginCall call) {
        String imageUrl = call.getString("imageUrl");
        String packageName = call.getString("packageName");
        String fileName = call.getString("fileName", "VietQR_" + System.currentTimeMillis() + ".png");
        
        // Thông tin chuyển khoản để tạo VietQR URI
        String accountNo = call.getString("accountNo", "");
        String bankBin = call.getString("bankBin", "");
        String amount = call.getString("amount", "");
        String content = call.getString("content", "");
        
        Log.d(TAG, "openQRInBankApp: package=" + packageName);
        
        new Thread(() -> {
            try {
                // 1. Tải và lưu ảnh QR
                java.net.URL url = new java.net.URL(imageUrl);
                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
                conn.setDoInput(true);
                conn.connect();
                android.graphics.Bitmap bitmap = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());
                
                if (bitmap == null) {
                    getActivity().runOnUiThread(() -> {
                        JSObject ret = new JSObject();
                        ret.put("success", false);
                        ret.put("error", "Download failed");
                        call.resolve(ret);
                    });
                    return;
                }
                
                // 2. Lưu vào MediaStore
                android.net.Uri savedUri = null;
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                    android.content.ContentValues values = new android.content.ContentValues();
                    values.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, fileName);
                    values.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/png");
                    values.put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, android.os.Environment.DIRECTORY_PICTURES + "/VietQR");
                    
                    savedUri = getActivity().getContentResolver().insert(
                        android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                    
                    if (savedUri != null) {
                        java.io.OutputStream out = getActivity().getContentResolver().openOutputStream(savedUri);
                        bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
                        out.close();
                    }
                } else {
                    java.io.File dir = new java.io.File(android.os.Environment.getExternalStoragePublicDirectory(
                        android.os.Environment.DIRECTORY_PICTURES), "VietQR");
                    if (!dir.exists()) dir.mkdirs();
                    
                    java.io.File file = new java.io.File(dir, fileName);
                    java.io.FileOutputStream out = new java.io.FileOutputStream(file);
                    bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out);
                    out.close();
                    
                    savedUri = android.net.Uri.fromFile(file);
                    
                    Intent scanIntent = new Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE);
                    scanIntent.setData(savedUri);
                    getActivity().sendBroadcast(scanIntent);
                }
                
                Log.d(TAG, "QR saved: " + savedUri);
                
                final android.net.Uri finalUri = savedUri;
                
                getActivity().runOnUiThread(() -> {
                    boolean opened = false;
                    String method = "";
                    
                    try {
                        // Phương pháp 1: Thử mở bằng VietQR scheme với bank app
                        String vietqrScheme = "vietqr://pay?app=" + getBankBinFromPackage(packageName) + 
                            "&ba=" + bankBin + "-" + accountNo + 
                            "&am=" + amount + 
                            "&tn=" + android.net.Uri.encode(content);
                        
                        Intent vietqrIntent = new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(vietqrScheme));
                        vietqrIntent.setPackage(packageName);
                        vietqrIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                        
                        try {
                            getActivity().startActivity(vietqrIntent);
                            opened = true;
                            method = "vietqr_scheme";
                            Log.d(TAG, "Opened via vietqr scheme");
                        } catch (Exception e) {
                            Log.d(TAG, "vietqr scheme failed: " + e.getMessage());
                        }
                        
                        // Phương pháp 2: Thử deep link với QR data
                        if (!opened) {
                            String qrData = "00020101021238570010A00000072701270006970422011" + accountNo.length() + accountNo + 
                                "0208QRIBFTTA5303704" + (amount.isEmpty() ? "" : "5405" + amount) + 
                                "5802VN62" + String.format("%02d", content.length() + 4) + "0804" + content + "6304";
                            
                            String qrScheme = getQRSchemeForBank(packageName) + "://qr?data=" + android.net.Uri.encode(qrData);
                            Intent qrIntent = new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(qrScheme));
                            qrIntent.setPackage(packageName);
                            qrIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                            
                            try {
                                getActivity().startActivity(qrIntent);
                                opened = true;
                                method = "qr_data_scheme";
                                Log.d(TAG, "Opened via QR data scheme");
                            } catch (Exception e) {
                                Log.d(TAG, "QR data scheme failed: " + e.getMessage());
                            }
                        }
                        
                        // Phương pháp 3: Mở app và để QR trong gallery
                        if (!opened) {
                            Intent launchIntent = getActivity().getPackageManager().getLaunchIntentForPackage(packageName);
                            if (launchIntent != null) {
                                launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                                getActivity().startActivity(launchIntent);
                                opened = true;
                                method = "app_launch";
                            }
                        }
                        
                    } catch (Exception e) {
                        Log.e(TAG, "Open error", e);
                    }
                    
                    JSObject ret = new JSObject();
                    ret.put("success", opened);
                    ret.put("method", method);
                    ret.put("savedUri", finalUri != null ? finalUri.toString() : "");
                    call.resolve(ret);
                });
                
            } catch (Exception e) {
                Log.e(TAG, "openQRInBankApp error", e);
                getActivity().runOnUiThread(() -> {
                    JSObject ret = new JSObject();
                    ret.put("success", false);
                    ret.put("error", e.getMessage());
                    call.resolve(ret);
                });
            }
        }).start();
    }
    
    // Lấy bank BIN từ package name - Danh sách đầy đủ các ngân hàng VN
    private String getBankBinFromPackage(String packageName) {
        if (packageName == null) return "";
        switch (packageName) {
            case "com.mbmobile": return "970422"; // MB Bank
            case "com.VCB": return "970436"; // Vietcombank
            case "vn.com.techcombank.bb.app": return "970407"; // Techcombank
            case "com.vnpay.bidv": return "970418"; // BIDV
            case "com.vietinbank.ipay": return "970415"; // Vietinbank
            case "com.vnpay.vpbankonline": return "970432"; // VPBank
            case "com.tpb.mb.gprsandroid": return "970423"; // TPBank
            case "mobile.acb.com.vn": return "970416"; // ACB
            case "com.sacombank.ewallet": return "970403"; // Sacombank Pay
            case "com.shb.smartbanking": return "970443"; // SHB Mobile Banking
            case "com.vnpay.hdbank": return "970437"; // HDBank
            case "com.ocb.ocbmb": return "970448"; // OCB OMNI
            case "vn.msb.smartbanking.msbmbank": return "970426"; // MSB mBank
            case "com.vib.myvib2": return "970441"; // VIB
            case "com.vnpay.agribankmobile": return "970405"; // Agribank E-Mobile Banking
            // Thêm các ngân hàng khác
            case "com.eximbank.mobilebanking": return "970431"; // Eximbank
            case "com.namabank.mobilebanking": return "970428"; // Nam A Bank
            case "vn.com.seabank.mb": return "970440"; // SeABank
            case "com.abbank.mobile": return "970425"; // ABBank
            case "com.vnpay.bvbank": return "970438"; // BaoViet Bank
            case "vn.kienlongbank.mobile": return "970452"; // Kienlongbank
            case "com.lpbank.mobilebanking": return "970449"; // LPBank (LienViet)
            case "com.ncb.mobilebanking": return "970419"; // NCB
            case "com.pgbank.pgbankmobile": return "970430"; // PGBank
            case "com.publicbank.bpmb": return "970439"; // Public Bank VN
            case "com.scb.smartbanking": return "970429"; // SCB
            case "com.uob.mobilebanking": return "970458"; // UOB Vietnam
            case "vn.wooribank.smart": return "970457"; // Woori Bank VN
            default: return "";
        }
    }
    
    // Lấy QR scheme cho từng ngân hàng
    private String getQRSchemeForBank(String packageName) {
        if (packageName == null) return "bank";
        switch (packageName) {
            case "com.mbmobile": return "mbbank";
            case "com.VCB": return "vcbdigibank";
            case "vn.com.techcombank.bb.app": return "techcombank";
            case "com.vnpay.bidv": return "bidvsmartbanking";
            case "com.vietinbank.ipay": return "vietinbank";
            case "com.vnpay.vpbankonline": return "vpbank";
            case "com.tpb.mb.gprsandroid": return "tpb";
            case "mobile.acb.com.vn": return "acbone";
            case "com.sacombank.ewallet": return "sacompay";
            case "com.shb.smartbanking": return "shbmobile";
            case "com.vnpay.hdbank": return "hdbank";
            case "com.ocb.ocbmb": return "ocbomni";
            case "vn.msb.smartbanking.msbmbank": return "msb";
            case "com.vib.myvib2": return "myvib";
            case "com.vnpay.agribankmobile": return "agribank";
            case "com.eximbank.mobilebanking": return "eximbank";
            case "vn.com.seabank.mb": return "seabank";
            case "com.lpbank.mobilebanking": return "lpbank";
            default: return "bank";
        }
    }
}
