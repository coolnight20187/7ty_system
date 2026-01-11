package com.ty7.smsreader;

import android.Manifest;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;

import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * Capacitor Plugin để quản lý đọc SMS ngân hàng
 */
@CapacitorPlugin(
    name = "SMSReader",
    permissions = {
        @Permission(
            alias = "sms",
            strings = {
                Manifest.permission.RECEIVE_SMS,
                Manifest.permission.READ_SMS
            }
        ),
        @Permission(
            alias = "notifications",
            strings = {
                Manifest.permission.POST_NOTIFICATIONS
            }
        )
    }
)
public class SMSReaderPlugin extends Plugin {
    
    private static final String TAG = "SMSReaderPlugin";
    private static final String PREFS_NAME = "SMSReaderPrefs";
    private static final String KEY_ENABLED = "sms_reading_enabled";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_AUTH_TOKEN = "auth_token";
    
    private PluginCall savedCall;
    
    /**
     * Kiểm tra quyền SMS
     */
    @PluginMethod
    public void checkPermissions(PluginCall call) {
        JSObject result = new JSObject();
        
        boolean hasSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.RECEIVE_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        boolean hasReadSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.READ_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        boolean hasNotificationPermission = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasNotificationPermission = ContextCompat.checkSelfPermission(
                getContext(), 
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED;
        }
        
        result.put("receiveSMS", hasSMSPermission ? "granted" : "denied");
        result.put("readSMS", hasReadSMSPermission ? "granted" : "denied");
        result.put("notifications", hasNotificationPermission ? "granted" : "denied");
        result.put("allGranted", hasSMSPermission && hasReadSMSPermission && hasNotificationPermission);
        
        call.resolve(result);
    }
    
    /**
     * Yêu cầu quyền SMS
     */
    @PluginMethod
    public void requestPermissions(PluginCall call) {
        savedCall = call;
        
        // Request SMS permissions
        requestPermissionForAlias("sms", call, "smsPermissionCallback");
    }
    
    @PermissionCallback
    private void smsPermissionCallback(PluginCall call) {
        if (call == null) {
            call = savedCall;
        }
        
        // Request notification permission if needed
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requestPermissionForAlias("notifications", call, "notificationPermissionCallback");
        } else {
            returnPermissionResult(call);
        }
    }
    
    @PermissionCallback
    private void notificationPermissionCallback(PluginCall call) {
        if (call == null) {
            call = savedCall;
        }
        returnPermissionResult(call);
    }
    
    private void returnPermissionResult(PluginCall call) {
        JSObject result = new JSObject();
        
        boolean hasSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.RECEIVE_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        boolean hasReadSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.READ_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        boolean hasNotificationPermission = true;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasNotificationPermission = ContextCompat.checkSelfPermission(
                getContext(), 
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED;
        }
        
        result.put("receiveSMS", hasSMSPermission ? "granted" : "denied");
        result.put("readSMS", hasReadSMSPermission ? "granted" : "denied");
        result.put("notifications", hasNotificationPermission ? "granted" : "denied");
        result.put("allGranted", hasSMSPermission && hasReadSMSPermission && hasNotificationPermission);
        
        call.resolve(result);
    }
    
    /**
     * Bật tính năng đọc SMS
     */
    @PluginMethod
    public void enableSMSReading(PluginCall call) {
        String serverUrl = call.getString("serverUrl", "");
        String authToken = call.getString("authToken", "");
        
        if (serverUrl.isEmpty()) {
            call.reject("Server URL is required");
            return;
        }
        
        // Kiểm tra quyền
        boolean hasSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.RECEIVE_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        if (!hasSMSPermission) {
            call.reject("SMS permission is required. Please grant permission first.");
            return;
        }
        
        // Lưu cấu hình
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        editor.putBoolean(KEY_ENABLED, true);
        editor.putString(KEY_SERVER_URL, serverUrl);
        editor.putString(KEY_AUTH_TOKEN, authToken);
        editor.apply();
        
        Log.i(TAG, "SMS reading enabled, server: " + serverUrl);
        
        JSObject result = new JSObject();
        result.put("enabled", true);
        result.put("serverUrl", serverUrl);
        call.resolve(result);
    }
    
    /**
     * Tắt tính năng đọc SMS
     */
    @PluginMethod
    public void disableSMSReading(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        editor.putBoolean(KEY_ENABLED, false);
        editor.apply();
        
        Log.i(TAG, "SMS reading disabled");
        
        JSObject result = new JSObject();
        result.put("enabled", false);
        call.resolve(result);
    }
    
    /**
     * Lấy trạng thái hiện tại
     */
    @PluginMethod
    public void getStatus(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean isEnabled = prefs.getBoolean(KEY_ENABLED, false);
        String serverUrl = prefs.getString(KEY_SERVER_URL, "");
        
        boolean hasSMSPermission = ContextCompat.checkSelfPermission(
            getContext(), 
            Manifest.permission.RECEIVE_SMS
        ) == PackageManager.PERMISSION_GRANTED;
        
        JSObject result = new JSObject();
        result.put("enabled", isEnabled);
        result.put("hasPermission", hasSMSPermission);
        result.put("serverUrl", serverUrl);
        result.put("isRunning", isEnabled && hasSMSPermission);
        
        call.resolve(result);
    }
    
    /**
     * Cập nhật cấu hình server
     */
    @PluginMethod
    public void updateConfig(PluginCall call) {
        String serverUrl = call.getString("serverUrl", "");
        String authToken = call.getString("authToken", "");
        
        if (serverUrl.isEmpty()) {
            call.reject("Server URL is required");
            return;
        }
        
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences.Editor editor = prefs.edit();
        editor.putString(KEY_SERVER_URL, serverUrl);
        if (!authToken.isEmpty()) {
            editor.putString(KEY_AUTH_TOKEN, authToken);
        }
        editor.apply();
        
        JSObject result = new JSObject();
        result.put("serverUrl", serverUrl);
        result.put("updated", true);
        call.resolve(result);
    }
    
    /**
     * Test gửi SMS thủ công (dùng để test)
     */
    @PluginMethod
    public void testSendSMS(PluginCall call) {
        String message = call.getString("message", "Test SMS from 7TY Agent");
        long amount = call.getInt("amount", 100000);
        String content = call.getString("content", "NAP 7TY001");
        
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String serverUrl = prefs.getString(KEY_SERVER_URL, "");
        String authToken = prefs.getString(KEY_AUTH_TOKEN, "");
        
        if (serverUrl.isEmpty()) {
            call.reject("Server URL is not configured");
            return;
        }
        
        // Simulate sending SMS data to server
        new Thread(() -> {
            try {
                java.net.URL url = new java.net.URL(serverUrl + "/api/v1/bank-webhook");
                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("X-Webhook-Source", "7ty-sms-reader-test");
                conn.setRequestProperty("X-Webhook-Secret", "7ty_sms_secret_2024");
                conn.setDoOutput(true);
                
                org.json.JSONObject payload = new org.json.JSONObject();
                payload.put("source", "sms_test");
                payload.put("bank_code", "MB");
                payload.put("amount", amount);
                payload.put("content", content);
                payload.put("transaction_id", "TEST_" + System.currentTimeMillis());
                payload.put("transaction_type", "deposit");
                payload.put("raw_message", message);
                
                java.io.OutputStream os = conn.getOutputStream();
                os.write(payload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
                os.close();
                
                int responseCode = conn.getResponseCode();
                
                getActivity().runOnUiThread(() -> {
                    JSObject result = new JSObject();
                    result.put("success", responseCode == 200);
                    result.put("responseCode", responseCode);
                    call.resolve(result);
                });
                
                conn.disconnect();
                
            } catch (Exception e) {
                getActivity().runOnUiThread(() -> {
                    call.reject("Error: " + e.getMessage());
                });
            }
        }).start();
    }
}

