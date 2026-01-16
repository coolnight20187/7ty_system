package com.ty7.smsreader;

import android.app.Notification;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import android.util.Log;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Notification Listener Service - Đọc thông báo từ app ngân hàng
 * 
 * Hỗ trợ các app ngân hàng:
 * - ACB (com.acb.acbmobile / vn.com.acb.acbmobile)
 * - MB Bank (com.mbmobile / vn.com.mbbank.mb)
 * - Vietcombank (com.VCB)
 * - Techcombank (vn.com.techcombank.bb.app)
 * - VPBank (com.vnpay.vpbankonline)
 * - TPBank (vn.tpb.mb.gprsandroid)
 * - BIDV (com.vnpay.bidv)
 * - VietinBank (com.vietinbank.ipay)
 * - Sacombank (vn.stb.mbanking)
 * - Momo (com.mservice.momotransfer)
 */
public class BankNotificationService extends NotificationListenerService {
    
    private static final String TAG = "BankNotificationService";
    private static final String PREFS_NAME = "SMSReaderPrefs";
    private static final String KEY_ENABLED = "notification_reading_enabled";
    private static final String KEY_SERVER_URL = "server_url";
    
    // Mapping package name -> Bank code
    // v2.52.0: CHỈ HỖ TRỢ ACB - Theo yêu cầu chỉ đọc notification từ ACB
    private static final Map<String, String> BANK_PACKAGES = new HashMap<String, String>() {{
        // ACB - Asia Commercial Bank (CHỈ HỖ TRỢ DUY NHẤT ACB)
        put("com.acb.acbmobile", "ACB");
        put("vn.com.acb.acbmobile", "ACB");
        put("com.acb.one", "ACB");
        put("com.acb", "ACB");
        put("vn.acb.acbmobile", "ACB");
        put("com.acb.acb", "ACB");
        put("mobile.acb.com.vn", "ACB");  // ACB Mobile app
        put("vn.acb.app", "ACB");  // ACB app variant
        put("com.acb.mobile", "ACB");  // ACB mobile variant
    }};
    
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private static BankNotificationService instance;
    private static String staticServerUrl = "";
    
    // Statistics
    private static int totalProcessed = 0;
    private static int successCount = 0;
    private static long totalAmount = 0;
    
    // v2.51.0: Deduplication cache để tránh xử lý notification trùng
    // Key: hash của (bankCode + amount + content), Value: timestamp
    private static final Map<String, Long> processedNotifications = new java.util.concurrent.ConcurrentHashMap<>();
    private static final long DEDUP_WINDOW_MS = 60000; // 60 giây - không xử lý notification giống nhau trong 60s
    
    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        Log.i(TAG, "BankNotificationService created");
        
        // Load saved server URL
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        staticServerUrl = prefs.getString(KEY_SERVER_URL, "");
        
        // v2.51.0: Cleanup cache cũ định kỳ
        cleanupOldDedupCache();
    }
    
    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        Log.i(TAG, "BankNotificationService destroyed");
    }
    
    public static BankNotificationService getInstance() {
        return instance;
    }
    
    public static boolean isServiceRunning() {
        return instance != null;
    }
    
    public static int getTotalProcessed() {
        return totalProcessed;
    }
    
    public static int getSuccessCount() {
        return successCount;
    }
    
    public static long getTotalAmount() {
        return totalAmount;
    }
    
    public static void setServerUrl(String url) {
        staticServerUrl = url;
        if (instance != null) {
            instance.getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_SERVER_URL, url)
                .apply();
        }
    }
    
    public static String getServerUrl() {
        return staticServerUrl;
    }
    
    // Debug log storage
    private static java.util.List<String> debugLogs = new java.util.ArrayList<>();
    private static final int MAX_DEBUG_LOGS = 100;
    
    private void saveDebugLog(String message) {
        String timestamp = new SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(new Date());
        String log = timestamp + " | " + message;
        debugLogs.add(0, log);
        if (debugLogs.size() > MAX_DEBUG_LOGS) {
            debugLogs.remove(debugLogs.size() - 1);
        }
        Log.d(TAG, "Debug: " + message);
    }
    
    public static java.util.List<String> getDebugLogs() {
        return new java.util.ArrayList<>(debugLogs);
    }
    
    public static void clearDebugLogs() {
        debugLogs.clear();
    }
    
    /**
     * v2.51.0: Cleanup cache dedup cũ
     */
    private void cleanupOldDedupCache() {
        long now = System.currentTimeMillis();
        processedNotifications.entrySet().removeIf(entry -> 
            now - entry.getValue() > DEDUP_WINDOW_MS * 5);
    }
    
    /**
     * v2.51.0: Kiểm tra notification đã xử lý chưa (deduplication)
     * @return true nếu notification mới, false nếu đã xử lý
     */
    private boolean isNewNotification(String bankCode, long amount, String content) {
        // Tạo hash key từ thông tin quan trọng
        String key = bankCode + "|" + amount + "|" + content.hashCode();
        long now = System.currentTimeMillis();
        
        Long lastProcessed = processedNotifications.get(key);
        if (lastProcessed != null && (now - lastProcessed) < DEDUP_WINDOW_MS) {
            Log.w(TAG, "⚠️ DUPLICATE NOTIFICATION DETECTED - Skipping!");
            Log.w(TAG, "Key: " + key + ", Last processed: " + (now - lastProcessed) + "ms ago");
            saveDebugLog("DUPLICATE SKIPPED: " + bankCode + " " + amount + "đ");
            return false;
        }
        
        // Đánh dấu đã xử lý
        processedNotifications.put(key, now);
        
        // Cleanup cache định kỳ
        if (processedNotifications.size() > 50) {
            cleanupOldDedupCache();
        }
        
        return true;
    }
    
    /**
     * Static method to send transaction to server - can be called from Plugin for testing
     */
    public static String sendTransactionToServer(
            android.content.Context context,
            String type,
            long amount,
            String content,
            String reference,
            String bankCode,
            String source) {
        
        try {
            SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
            String serverUrl = prefs.getString(KEY_SERVER_URL, staticServerUrl);
            
            if (serverUrl.isEmpty()) {
                serverUrl = "https://cautious-space-fortnight-j7rwrvr6j9g3p5gw-8000.app.github.dev";
            }
            
            JSONObject payload = new JSONObject();
            payload.put("type", type);
            payload.put("amount", amount);
            payload.put("content", content);
            payload.put("reference", reference);
            payload.put("bank_code", bankCode);
            payload.put("source", source);
            payload.put("timestamp", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date()));
            
            URL url = new URL(serverUrl + "/api/v1/bank-webhook");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(15000);
            
            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = payload.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input, 0, input.length);
            }
            
            int responseCode = conn.getResponseCode();
            
            java.io.InputStream is = responseCode >= 400 ? conn.getErrorStream() : conn.getInputStream();
            java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.InputStreamReader(is));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            conn.disconnect();
            
            return response.toString();
            
        } catch (Exception e) {
            Log.e(TAG, "Error in sendTransactionToServer", e);
            return "{\"success\": false, \"error\": \"" + e.getMessage() + "\"}";
        }
    }
    
    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        if (sbn == null) return;
        
        String packageName = sbn.getPackageName();
        
        // DEBUG: Log tất cả notifications để debug
        Log.i(TAG, "=== NOTIFICATION RECEIVED ===");
        Log.i(TAG, "Package: " + packageName);
        
        // Lấy nội dung notification để log
        Notification notification = sbn.getNotification();
        Bundle extras = notification.extras;
        
        String title = "";
        String text = "";
        String bigText = "";
        String subText = "";
        String infoText = "";
        String summaryText = "";
        String tickerText = "";
        
        if (extras != null) {
            CharSequence titleCs = extras.getCharSequence(Notification.EXTRA_TITLE);
            CharSequence textCs = extras.getCharSequence(Notification.EXTRA_TEXT);
            CharSequence bigTextCs = extras.getCharSequence(Notification.EXTRA_BIG_TEXT);
            CharSequence subTextCs = extras.getCharSequence(Notification.EXTRA_SUB_TEXT);
            CharSequence infoTextCs = extras.getCharSequence(Notification.EXTRA_INFO_TEXT);
            CharSequence summaryTextCs = extras.getCharSequence(Notification.EXTRA_SUMMARY_TEXT);
            
            if (titleCs != null) title = titleCs.toString();
            if (textCs != null) text = textCs.toString();
            if (bigTextCs != null) bigText = bigTextCs.toString();
            if (subTextCs != null) subText = subTextCs.toString();
            if (infoTextCs != null) infoText = infoTextCs.toString();
            if (summaryTextCs != null) summaryText = summaryTextCs.toString();
        }
        
        // Lấy ticker text
        if (notification.tickerText != null) {
            tickerText = notification.tickerText.toString();
        }
        
        Log.i(TAG, "Title: " + title);
        Log.i(TAG, "Text: " + text);
        Log.i(TAG, "BigText: " + bigText);
        Log.i(TAG, "SubText: " + subText);
        Log.i(TAG, "TickerText: " + tickerText);
        
        // Kiểm tra có phải app ngân hàng không
        String bankCode = BANK_PACKAGES.get(packageName);
        if (bankCode == null) {
            Log.d(TAG, "Not a bank app, skipping: " + packageName);
            // Save to debug log for unknown packages
            saveDebugLog("Unknown package: " + packageName + " | " + title + " | " + text);
            return;
        }
        
        Log.i(TAG, "Bank detected: " + bankCode);
        
        // Kiểm tra tính năng có được bật không
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        boolean isEnabled = prefs.getBoolean(KEY_ENABLED, true); // Default enabled
        
        if (!isEnabled) {
            Log.d(TAG, "Notification reading is disabled");
            return;
        }
        
        // Combine content - ưu tiên bigText vì thường chứa nội dung đầy đủ
        // Sau đó là tickerText (thường có full content)
        String content;
        if (bigText != null && !bigText.trim().isEmpty()) {
            content = bigText.trim();
        } else if (tickerText != null && !tickerText.trim().isEmpty() && tickerText.length() > text.length()) {
            content = tickerText.trim();
        } else {
            // Fallback: combine tất cả
            content = (title + " " + text + " " + subText + " " + infoText).trim();
        }
        
        // Nếu content quá ngắn, thử combine nhiều nguồn
        if (content.length() < 50) {
            String combined = (title + " " + text + " " + bigText + " " + tickerText + " " + subText).trim();
            combined = combined.replaceAll("\\s+", " ");
            if (combined.length() > content.length()) {
                content = combined;
            }
        }
        
        if (content.isEmpty()) {
            return;
        }
        
        Log.i(TAG, "Bank notification from " + bankCode + ": " + content);
        
        // Parse thông tin giao dịch
        TransactionInfo txInfo = parseTransactionFromNotification(content, bankCode);
        
        if (txInfo == null) {
            Log.d(TAG, "Could not parse transaction from notification");
            return;
        }
        
        // Chỉ xử lý giao dịch tiền vào
        if (!txInfo.isCredit) {
            Log.d(TAG, "Skipping debit transaction");
            return;
        }
        
        // v2.51.0: Kiểm tra duplicate notification
        if (!isNewNotification(bankCode, txInfo.amount, content)) {
            Log.w(TAG, "Skipping duplicate notification");
            return;
        }
        
        // Gửi lên server
        sendToServer(txInfo, content, bankCode);
    }
    
    @Override
    public void onNotificationRemoved(StatusBarNotification sbn) {
        // Không cần xử lý
    }
    
    /**
     * Parse thông tin giao dịch từ notification
     */
    private TransactionInfo parseTransactionFromNotification(String content, String bankCode) {
        TransactionInfo info = new TransactionInfo();
        info.bankCode = bankCode;
        info.rawContent = content;
        
        String upperContent = content.toUpperCase();
        
        // Detect loại giao dịch (tiền vào / tiền ra)
        // ACB format: "TK 123456789 +100,000 VND lúc 12:30 12/01/2026. ND: NAP 7TY001. SD: 500,000 VND"
        // MB format: "TK: 123456789 + 100,000 VND. Nội dung: NAP 7TY001. Số dư: 500,000 VND"
        
        // Check for credit indicators
        if (upperContent.contains("+") || 
            upperContent.contains("NHẬN") ||
            upperContent.contains("NHAN") ||
            upperContent.contains("CREDITED") ||
            upperContent.contains("TIỀN VÀO") ||
            upperContent.contains("TIEN VAO") ||
            upperContent.contains("GHI CÓ") ||
            upperContent.contains("GHI CO")) {
            info.isCredit = true;
        } else if (upperContent.contains("-") ||
                   upperContent.contains("CHUYỂN") ||
                   upperContent.contains("CHUYEN") ||
                   upperContent.contains("DEBITED") ||
                   upperContent.contains("TIỀN RA") ||
                   upperContent.contains("TIEN RA") ||
                   upperContent.contains("GHI NỢ") ||
                   upperContent.contains("GHI NO") ||
                   upperContent.contains("THANH TOÁN") ||
                   upperContent.contains("THANH TOAN")) {
            info.isCredit = false;
        } else {
            // Default: try to detect from amount sign
            Pattern signPattern = Pattern.compile("([+-])\\s*[\\d,.]+");
            Matcher signMatcher = signPattern.matcher(content);
            if (signMatcher.find()) {
                info.isCredit = "+".equals(signMatcher.group(1));
            } else {
                // Cannot determine, assume credit if amount found
                info.isCredit = true;
            }
        }
        
        // Parse amount - ACB specific patterns first
        Pattern[] amountPatterns = {
            // ACB: +100,000 VND or -100,000 VND
            Pattern.compile("[+-]\\s*([\\d,\\.]+)\\s*(?:VND|VNĐ|đ|d)", Pattern.CASE_INSENSITIVE),
            // General: Số tiền: 100,000
            Pattern.compile("(?:Số tiền|So tien|Amount)[:\\s]*([\\d,\\.]+)", Pattern.CASE_INSENSITIVE),
            // With currency: 100,000 VND
            Pattern.compile("([\\d,\\.]+)\\s*(?:VND|VNĐ|đ)", Pattern.CASE_INSENSITIVE),
            // Just numbers with comma (at least 4 digits)
            Pattern.compile("\\b([\\d]{1,3}(?:,[\\d]{3})+)\\b"),
        };
        
        for (Pattern pattern : amountPatterns) {
            Matcher matcher = pattern.matcher(content);
            if (matcher.find()) {
                String amountStr = matcher.group(1)
                    .replace(",", "")
                    .replace(".", "")
                    .trim();
                try {
                    info.amount = Long.parseLong(amountStr);
                    if (info.amount > 0) break;
                } catch (NumberFormatException e) {
                    // Continue to next pattern
                }
            }
        }
        
        if (info.amount <= 0) {
            return null; // No valid amount found
        }
        
        // Parse nội dung chuyển khoản
        // Format chuẩn từ app Đại lý: NAP {agent_code} {amount}
        // Ví dụ: NAP AG000001 1000000, NAP 7TY001 5000000
        // ACB format thực tế: GD: NAP AG000001 101000 GD 6016IBT1iJQTWDL8 160126-09:12:53
        // - Nội dung nằm sau "GD:" và trước "GD " (space) hoặc trước timestamp
        Pattern[] contentPatterns = {
            // ACB specific: GD: NAP AG000001 101000 GD 6016... (nội dung nằm giữa "GD:" và "GD ")
            Pattern.compile("GD:\\s*(.+?)\\s+GD\\s+[A-Z0-9]", Pattern.CASE_INSENSITIVE),
            // ACB fallback: GD: content (đến cuối hoặc đến timestamp)
            Pattern.compile("GD:\\s*(.+?)(?:\\s+\\d{6}-|$)", Pattern.CASE_INSENSITIVE),
            // Standard format: ND: NAP AG000001 1000000
            Pattern.compile("(?:ND|Nội dung|Noi dung|Content|Memo)[:\\s]*(.+?)(?:\\.|SD|Số dư|$)", Pattern.CASE_INSENSITIVE),
            // Format chuẩn app: NAP AG000001 1000000 (capture full content)
            Pattern.compile("((?:NAP|NAPTIEN|TOPUP)\\s+[A-Z0-9]+(?:\\s+\\d+)?)", Pattern.CASE_INSENSITIVE),
            // Just agent code format
            Pattern.compile("(?:NAP|NAPTIEN|TOPUP)\\s+([A-Z0-9]+)", Pattern.CASE_INSENSITIVE),
        };
        
        for (Pattern pattern : contentPatterns) {
            Matcher matcher = pattern.matcher(content);
            if (matcher.find()) {
                info.transferContent = matcher.group(1).trim();
                break;
            }
        }
        
        // Parse account number
        Pattern accountPattern = Pattern.compile("(?:TK|Tài khoản|Tai khoan|Account)[:\\s]*([\\d]+)", Pattern.CASE_INSENSITIVE);
        Matcher accountMatcher = accountPattern.matcher(content);
        if (accountMatcher.find()) {
            info.accountNumber = accountMatcher.group(1);
        }
        
        // Parse balance
        Pattern balancePattern = Pattern.compile("(?:SD|Số dư|So du|Balance)[:\\s]*([\\d,\\.]+)", Pattern.CASE_INSENSITIVE);
        Matcher balanceMatcher = balancePattern.matcher(content);
        if (balanceMatcher.find()) {
            String balanceStr = balanceMatcher.group(1)
                .replace(",", "")
                .replace(".", "");
            try {
                info.balance = Long.parseLong(balanceStr);
            } catch (NumberFormatException e) {
                // Ignore
            }
        }
        
        // Parse mã giao dịch (transaction reference) từ ACB và các ngân hàng khác
        // ACB format thực tế: GD: NAP AG000001 101000 GD 6016IBT1iJQTWDL8 160126-09:12:53
        // - Mã GD là chuỗi sau "GD " (có space, KHÔNG có dấu :) + dãy ký tự
        // MB format: Mã GD: FT12345678
        // VCB format: Ref: 123456789
        Pattern[] transactionRefPatterns = {
            // ACB specific: "GD 6016IBT1iJQTWDL8" (sau GD + space, KHÔNG có dấu :)
            Pattern.compile("\\sGD\\s+([A-Z0-9]{10,})", Pattern.CASE_INSENSITIVE),
            // MB format: Mã GD: FT12345678
            Pattern.compile("(?:Mã GD|Ma GD)[:\\s]*(FT[0-9A-Z]+)", Pattern.CASE_INSENSITIVE),
            // Generic: FT + số
            Pattern.compile("(FT[0-9A-Z]+)", Pattern.CASE_INSENSITIVE),
            // 9-15 digit transaction code after certain keywords
            Pattern.compile("(?:TID|Trans ID|Ref No|Ref)[:\\s]*([0-9A-Z]{9,15})", Pattern.CASE_INSENSITIVE),
        };
        
        for (Pattern pattern : transactionRefPatterns) {
            Matcher matcher = pattern.matcher(content);
            if (matcher.find()) {
                info.transactionRef = matcher.group(1).trim();
                Log.i(TAG, "Found transaction ref: " + info.transactionRef);
                break;
            }
        }
        
        return info;
    }
    
    /**
     * Gửi thông tin giao dịch lên server
     */
    private void sendToServer(final TransactionInfo txInfo, final String rawContent, final String bankCode) {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        String serverUrl = prefs.getString(KEY_SERVER_URL, "");
        
        // Use default URL if not configured
        if (serverUrl.isEmpty()) {
            serverUrl = "https://cautious-space-fortnight-j7rwrvr6j9g3p5gw-8000.app.github.dev";
            Log.i(TAG, "Using default server URL: " + serverUrl);
        }
        
        final String finalServerUrl = serverUrl;
        
        executor.execute(new Runnable() {
            @Override
            public void run() {
                try {
                    // Build JSON payload
                    JSONObject payload = new JSONObject();
                    payload.put("type", "credit");
                    payload.put("amount", txInfo.amount);
                    
                    // Gửi raw content để server parse
                    payload.put("content", rawContent);
                    payload.put("transfer_content", txInfo.transferContent != null ? txInfo.transferContent : "");
                    
                    // v2.131.0: Sử dụng mã GD từ ngân hàng làm reference nếu có
                    // Mã GD ACB/MB/VCB sẽ được dùng làm mã giao dịch nạp tiền
                    String reference;
                    if (txInfo.transactionRef != null && !txInfo.transactionRef.isEmpty()) {
                        reference = bankCode + "_" + txInfo.transactionRef;
                        Log.i(TAG, "Using bank transaction ref: " + reference);
                    } else {
                        reference = "NOTIF_" + System.currentTimeMillis();
                    }
                    payload.put("reference", reference);
                    payload.put("bank_transaction_ref", txInfo.transactionRef != null ? txInfo.transactionRef : "");
                    
                    payload.put("bank_code", bankCode);
                    payload.put("account_number", txInfo.accountNumber != null ? txInfo.accountNumber : "");
                    payload.put("balance", txInfo.balance);
                    payload.put("raw_content", rawContent);
                    payload.put("source", "notification_reader");
                    payload.put("app_version", "2.53.0");
                    payload.put("timestamp", new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date()));
                    
                    // Send to server
                    URL url = new URL(finalServerUrl + "/api/v1/bank-webhook");
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
                    conn.setRequestProperty("X-Source", "notification-reader");
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(15000);
                    conn.setReadTimeout(15000);
                    
                    try (OutputStream os = conn.getOutputStream()) {
                        byte[] input = payload.toString().getBytes(StandardCharsets.UTF_8);
                        os.write(input, 0, input.length);
                    }
                    
                    int responseCode = conn.getResponseCode();
                    Log.i(TAG, "Server response: " + responseCode);
                    
                    totalProcessed++;
                    
                    if (responseCode == 200) {
                        Log.i(TAG, "Transaction sent successfully: " + txInfo.amount + " VND");
                        successCount++;
                        totalAmount += txInfo.amount;
                        
                        // Broadcast success to UI
                        android.content.Intent intent = new android.content.Intent("com.ty7.smsreader.TRANSACTION_PROCESSED");
                        intent.putExtra("bank_code", bankCode);
                        intent.putExtra("amount", txInfo.amount);
                        intent.putExtra("success", true);
                        sendBroadcast(intent);
                    }
                    
                    conn.disconnect();
                    
                } catch (Exception e) {
                    Log.e(TAG, "Error sending to server: " + e.getMessage());
                }
            }
        });
    }
    
    /**
     * Class chứa thông tin giao dịch
     */
    private static class TransactionInfo {
        String bankCode;
        long amount;
        String transferContent;
        String accountNumber;
        long balance;
        boolean isCredit;
        String rawContent;
        String transactionRef; // Mã giao dịch từ ngân hàng (GD: xxx)
    }
}
