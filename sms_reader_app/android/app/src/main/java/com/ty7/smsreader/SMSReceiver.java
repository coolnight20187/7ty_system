package com.ty7.smsreader;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.telephony.SmsMessage;
import android.util.Log;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * SMS Receiver - Nhận và xử lý SMS ngân hàng để auto-deposit
 * Hỗ trợ các ngân hàng: MB Bank, Vietcombank, Techcombank, VPBank, ACB, TPBank, BIDV, VietinBank, etc.
 */
public class SMSReceiver extends BroadcastReceiver {
    
    private static final String TAG = "SMSReceiver";
    private static final String PREFS_NAME = "SMSReaderPrefs";
    private static final String KEY_ENABLED = "sms_reading_enabled";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_AUTH_TOKEN = "auth_token";
    
    // Danh sách sender của các ngân hàng phổ biến
    private static final String[] BANK_SENDERS = {
        "MB Bank", "MBBANK", "MB", "MBBank",
        "Vietcombank", "VCB", "VIETCOMBANK",
        "Techcombank", "TCB", "TECHCOMBANK",
        "VPBank", "VPBANK", "VPB",
        "ACB", "ACBANK",
        "TPBank", "TPBANK", "TPB",
        "BIDV",
        "VietinBank", "VIETINBANK", "CTG",
        "Sacombank", "SACOMBANK", "STB",
        "HDBank", "HDBANK",
        "OCB",
        "MSB", "MSBBANK",
        "SHB",
        "VIB",
        "Agribank", "AGRIBANK",
        "SeABank", "SEABANK",
        "LienVietPostBank", "LVPB",
        "NamABank", "NAMABANK",
        "BacABank", "BACABANK",
        "Eximbank", "EIB",
        "ABBank", "ABBANK",
        "SCB",
        "PVcomBank", "PVCOMBANK"
    };
    
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || intent.getAction() == null) {
            return;
        }
        
        if (!intent.getAction().equals("android.provider.Telephony.SMS_RECEIVED")) {
            return;
        }
        
        // Kiểm tra xem tính năng đọc SMS có được bật không
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean isEnabled = prefs.getBoolean(KEY_ENABLED, false);
        
        if (!isEnabled) {
            Log.d(TAG, "SMS reading is disabled");
            return;
        }
        
        Bundle bundle = intent.getExtras();
        if (bundle == null) {
            return;
        }
        
        Object[] pdus = (Object[]) bundle.get("pdus");
        if (pdus == null || pdus.length == 0) {
            return;
        }
        
        String format = bundle.getString("format");
        StringBuilder messageBody = new StringBuilder();
        String sender = "";
        long timestamp = System.currentTimeMillis();
        
        for (Object pdu : pdus) {
            SmsMessage smsMessage;
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
                smsMessage = SmsMessage.createFromPdu((byte[]) pdu, format);
            } else {
                smsMessage = SmsMessage.createFromPdu((byte[]) pdu);
            }
            
            if (smsMessage != null) {
                messageBody.append(smsMessage.getMessageBody());
                sender = smsMessage.getOriginatingAddress();
                timestamp = smsMessage.getTimestampMillis();
            }
        }
        
        String fullMessage = messageBody.toString();
        
        // Kiểm tra xem SMS có phải từ ngân hàng không
        if (isBankSMS(sender, fullMessage)) {
            Log.d(TAG, "Bank SMS detected from: " + sender);
            processBankSMS(context, sender, fullMessage, timestamp);
        }
    }
    
    /**
     * Kiểm tra xem SMS có phải từ ngân hàng không
     */
    private boolean isBankSMS(String sender, String message) {
        if (sender == null) {
            return false;
        }
        
        // Kiểm tra sender
        String upperSender = sender.toUpperCase();
        for (String bankSender : BANK_SENDERS) {
            if (upperSender.contains(bankSender.toUpperCase())) {
                return true;
            }
        }
        
        // Kiểm tra nội dung SMS có chứa các từ khóa ngân hàng không
        String upperMessage = message.toUpperCase();
        if (upperMessage.contains("GD:") || 
            upperMessage.contains("SD:") ||
            upperMessage.contains("SO DU") ||
            upperMessage.contains("GIAO DICH") ||
            upperMessage.contains("CHUYEN KHOAN") ||
            upperMessage.contains("NHAN TIEN") ||
            upperMessage.contains("BIEN LAI") ||
            upperMessage.contains("TK:") ||
            upperMessage.contains("STK:") ||
            upperMessage.contains("VND") ||
            upperMessage.contains("+VND") ||
            upperMessage.contains("-VND")) {
            return true;
        }
        
        return false;
    }
    
    /**
     * Xử lý SMS ngân hàng
     */
    private void processBankSMS(Context context, String sender, String message, long timestamp) {
        executor.execute(() -> {
            try {
                SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
                String serverUrl = prefs.getString(KEY_SERVER_URL, "");
                String authToken = prefs.getString(KEY_AUTH_TOKEN, "");
                
                if (serverUrl.isEmpty()) {
                    Log.e(TAG, "Server URL is not configured");
                    return;
                }
                
                // Parse SMS để lấy thông tin
                BankSMSData smsData = parseBankSMS(sender, message, timestamp);
                
                if (smsData == null || !smsData.isDeposit) {
                    Log.d(TAG, "SMS is not a deposit transaction");
                    return;
                }
                
                // Gửi lên server
                sendToServer(serverUrl, authToken, smsData);
                
            } catch (Exception e) {
                Log.e(TAG, "Error processing bank SMS: " + e.getMessage());
            }
        });
    }
    
    /**
     * Parse SMS ngân hàng để lấy thông tin giao dịch
     */
    private BankSMSData parseBankSMS(String sender, String message, long timestamp) {
        BankSMSData data = new BankSMSData();
        data.sender = sender;
        data.rawMessage = message;
        data.timestamp = timestamp;
        
        String upperMessage = message.toUpperCase();
        
        // Kiểm tra xem có phải giao dịch tiền vào không (deposit)
        // Các pattern phổ biến:
        // - "+VND" hoặc "+ VND"
        // - "NHAN TIEN"
        // - "CHUYEN KHOAN DEN"
        // - "GD: +" (giao dịch cộng)
        
        boolean isDeposit = upperMessage.contains("+VND") ||
                           upperMessage.contains("+ VND") ||
                           upperMessage.contains("+") && upperMessage.contains("VND") ||
                           upperMessage.contains("NHAN TIEN") ||
                           upperMessage.contains("NHAN") && upperMessage.contains("VND") ||
                           upperMessage.contains("CHUYEN KHOAN DEN") ||
                           upperMessage.contains("GD: +") ||
                           upperMessage.contains("GD:+");
        
        // Loại trừ các giao dịch rút tiền
        boolean isWithdraw = upperMessage.contains("-VND") ||
                            upperMessage.contains("- VND") ||
                            upperMessage.contains("CHUYEN KHOAN DI") ||
                            upperMessage.contains("THANH TOAN") ||
                            upperMessage.contains("RUT TIEN") ||
                            upperMessage.contains("GD: -") ||
                            upperMessage.contains("GD:-");
        
        if (isWithdraw && !isDeposit) {
            data.isDeposit = false;
            return data;
        }
        
        data.isDeposit = isDeposit;
        
        // Parse số tiền
        data.amount = parseAmount(message);
        
        // Parse nội dung chuyển khoản
        data.content = parseContent(message);
        
        // Parse số tài khoản
        data.accountNumber = parseAccountNumber(message);
        
        // Parse ngân hàng
        data.bankCode = parseBankCode(sender, message);
        
        // Parse transaction ID
        data.transactionId = parseTransactionId(message);
        
        Log.d(TAG, "Parsed SMS: amount=" + data.amount + ", content=" + data.content + 
              ", bank=" + data.bankCode + ", isDeposit=" + data.isDeposit);
        
        return data;
    }
    
    /**
     * Parse số tiền từ SMS
     */
    private long parseAmount(String message) {
        // Các pattern số tiền phổ biến:
        // +1,000,000VND
        // +1.000.000 VND
        // GD: +1,000,000
        // So tien: 1000000
        
        // Pattern 1: +1,000,000VND hoặc +1.000.000VND
        Pattern pattern1 = Pattern.compile("\\+([\\d,\\.]+)\\s*VND", Pattern.CASE_INSENSITIVE);
        Matcher matcher1 = pattern1.matcher(message);
        if (matcher1.find()) {
            return parseNumberString(matcher1.group(1));
        }
        
        // Pattern 2: GD: +1,000,000
        Pattern pattern2 = Pattern.compile("GD:\\s*\\+([\\d,\\.]+)", Pattern.CASE_INSENSITIVE);
        Matcher matcher2 = pattern2.matcher(message);
        if (matcher2.find()) {
            return parseNumberString(matcher2.group(1));
        }
        
        // Pattern 3: So tien: 1,000,000
        Pattern pattern3 = Pattern.compile("(?:so\\s*tien|sotien|tien)\\s*:?\\s*([\\d,\\.]+)", Pattern.CASE_INSENSITIVE);
        Matcher matcher3 = pattern3.matcher(message);
        if (matcher3.find()) {
            return parseNumberString(matcher3.group(1));
        }
        
        // Pattern 4: Tìm số lớn nhất (có thể là số tiền)
        Pattern pattern4 = Pattern.compile("([\\d,\\.]{4,})", Pattern.CASE_INSENSITIVE);
        Matcher matcher4 = pattern4.matcher(message);
        long maxAmount = 0;
        while (matcher4.find()) {
            long amount = parseNumberString(matcher4.group(1));
            if (amount > maxAmount && amount >= 1000) {
                maxAmount = amount;
            }
        }
        
        return maxAmount;
    }
    
    /**
     * Chuyển string số thành long
     */
    private long parseNumberString(String numStr) {
        if (numStr == null || numStr.isEmpty()) {
            return 0;
        }
        // Remove comma, dot as thousand separator
        String cleaned = numStr.replaceAll("[,\\.]", "");
        try {
            return Long.parseLong(cleaned);
        } catch (NumberFormatException e) {
            return 0;
        }
    }
    
    /**
     * Parse nội dung chuyển khoản
     */
    private String parseContent(String message) {
        // Pattern 1: ND: nội dung hoặc Noi dung: nội dung
        Pattern pattern1 = Pattern.compile("(?:ND|NOI\\s*DUNG|NDCK|NOIDUNGCK)\\s*:?\\s*(.+?)(?:\\.|$|SD:|TK:|GD:)", Pattern.CASE_INSENSITIVE);
        Matcher matcher1 = pattern1.matcher(message);
        if (matcher1.find()) {
            return matcher1.group(1).trim();
        }
        
        // Pattern 2: Tìm sau "tu:" hoặc "từ:"
        Pattern pattern2 = Pattern.compile("(?:tu|từ)\\s*:?\\s*(.+?)(?:\\.|$|SD:|TK:|GD:)", Pattern.CASE_INSENSITIVE);
        Matcher matcher2 = pattern2.matcher(message);
        if (matcher2.find()) {
            return matcher2.group(1).trim();
        }
        
        return "";
    }
    
    /**
     * Parse số tài khoản
     */
    private String parseAccountNumber(String message) {
        // Pattern: TK: 123456789 hoặc STK: 123456789
        Pattern pattern = Pattern.compile("(?:TK|STK|TKKH)\\s*:?\\s*(\\d+)", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(message);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "";
    }
    
    /**
     * Parse mã ngân hàng từ sender
     */
    private String parseBankCode(String sender, String message) {
        String upper = (sender + " " + message).toUpperCase();
        
        if (upper.contains("MBBANK") || upper.contains("MB BANK") || 
            (upper.contains("MB") && !upper.contains("MSB"))) {
            return "MB";
        }
        if (upper.contains("VIETCOMBANK") || upper.contains("VCB")) {
            return "VCB";
        }
        if (upper.contains("TECHCOMBANK") || upper.contains("TCB")) {
            return "TCB";
        }
        if (upper.contains("VPBANK") || upper.contains("VPB")) {
            return "VPB";
        }
        if (upper.contains("ACB")) {
            return "ACB";
        }
        if (upper.contains("TPBANK") || upper.contains("TPB")) {
            return "TPB";
        }
        if (upper.contains("BIDV")) {
            return "BIDV";
        }
        if (upper.contains("VIETINBANK") || upper.contains("CTG")) {
            return "ICB";
        }
        if (upper.contains("SACOMBANK") || upper.contains("STB")) {
            return "STB";
        }
        if (upper.contains("HDBANK")) {
            return "HDB";
        }
        if (upper.contains("OCB")) {
            return "OCB";
        }
        if (upper.contains("MSB") || upper.contains("MSBBANK")) {
            return "MSB";
        }
        if (upper.contains("SHB")) {
            return "SHB";
        }
        if (upper.contains("VIB")) {
            return "VIB";
        }
        if (upper.contains("AGRIBANK")) {
            return "VBA";
        }
        if (upper.contains("SEABANK")) {
            return "SEAB";
        }
        if (upper.contains("EXIMBANK") || upper.contains("EIB")) {
            return "EIB";
        }
        
        return "UNKNOWN";
    }
    
    /**
     * Parse transaction ID
     */
    private String parseTransactionId(String message) {
        // Pattern: Ma GD: 123456 hoặc GD: 123456
        Pattern pattern = Pattern.compile("(?:MA\\s*GD|MAGD|GD|REF|MA\\s*CK|MACK)\\s*:?\\s*([A-Z0-9]+)", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(message);
        if (matcher.find()) {
            return matcher.group(1);
        }
        return "SMS_" + System.currentTimeMillis();
    }
    
    /**
     * Gửi dữ liệu lên server
     */
    private void sendToServer(String serverUrl, String authToken, BankSMSData data) {
        try {
            URL url = new URL(serverUrl + "/api/v1/bank-webhook");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("X-Webhook-Source", "7ty-sms-reader");
            conn.setRequestProperty("X-Webhook-Secret", "7ty_sms_secret_2024");
            
            if (!authToken.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + authToken);
            }
            
            conn.setDoOutput(true);
            conn.setConnectTimeout(30000);
            conn.setReadTimeout(30000);
            
            // Build JSON payload
            JSONObject payload = new JSONObject();
            payload.put("source", "sms");
            payload.put("bank_code", data.bankCode);
            payload.put("account_number", data.accountNumber);
            payload.put("amount", data.amount);
            payload.put("content", data.content);
            payload.put("transaction_id", data.transactionId);
            payload.put("transaction_type", "deposit");
            payload.put("raw_message", data.rawMessage);
            payload.put("sender", data.sender);
            
            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
            payload.put("transaction_date", sdf.format(new Date(data.timestamp)));
            
            byte[] input = payload.toString().getBytes(StandardCharsets.UTF_8);
            
            try (OutputStream os = conn.getOutputStream()) {
                os.write(input, 0, input.length);
            }
            
            int responseCode = conn.getResponseCode();
            Log.d(TAG, "Server response: " + responseCode);
            
            if (responseCode == 200) {
                Log.i(TAG, "SMS data sent successfully");
            } else {
                Log.e(TAG, "Failed to send SMS data, response code: " + responseCode);
            }
            
            conn.disconnect();
            
        } catch (Exception e) {
            Log.e(TAG, "Error sending to server: " + e.getMessage());
        }
    }
    
    /**
     * Data class cho SMS ngân hàng
     */
    private static class BankSMSData {
        String sender;
        String rawMessage;
        long timestamp;
        boolean isDeposit;
        long amount;
        String content;
        String accountNumber;
        String bankCode;
        String transactionId;
    }
}

