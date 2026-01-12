package com.ty7.smsreader;

import android.content.ComponentName;
import android.content.Intent;
import android.os.Build;
import android.provider.Settings;
import android.text.TextUtils;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * Capacitor Plugin for Notification Reader functionality.
 * This plugin provides methods to:
 * - Check if notification access is granted
 * - Open notification access settings
 * - Start/stop the notification listener service
 */
@CapacitorPlugin(name = "NotificationReader")
public class NotificationReaderPlugin extends Plugin {
    
    private static final String TAG = "NotificationReaderPlugin";
    
    /**
     * Check if the app has notification access permission
     */
    @PluginMethod
    public void hasNotificationAccess(PluginCall call) {
        try {
            boolean hasAccess = isNotificationServiceEnabled();
            JSObject result = new JSObject();
            result.put("granted", hasAccess);
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error checking notification access", e);
            call.reject("Error checking notification access: " + e.getMessage());
        }
    }
    
    /**
     * Open the notification access settings screen
     */
    @PluginMethod
    public void openNotificationSettings(PluginCall call) {
        try {
            Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            Log.e(TAG, "Error opening notification settings", e);
            call.reject("Error opening notification settings: " + e.getMessage());
        }
    }
    
    /**
     * Get the current status of the notification listener service
     */
    @PluginMethod
    public void getServiceStatus(PluginCall call) {
        try {
            boolean hasAccess = isNotificationServiceEnabled();
            boolean isRunning = BankNotificationService.isServiceRunning();
            
            JSObject result = new JSObject();
            result.put("hasAccess", hasAccess);
            result.put("isRunning", isRunning);
            result.put("totalProcessed", BankNotificationService.getTotalProcessed());
            result.put("successCount", BankNotificationService.getSuccessCount());
            result.put("totalAmount", BankNotificationService.getTotalAmount());
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error getting service status", e);
            call.reject("Error getting service status: " + e.getMessage());
        }
    }
    
    /**
     * Save the server URL configuration
     */
    @PluginMethod
    public void saveConfig(PluginCall call) {
        try {
            String serverUrl = call.getString("serverUrl");
            if (serverUrl == null || serverUrl.isEmpty()) {
                call.reject("Server URL is required");
                return;
            }
            
            // Save to SharedPreferences - use same key as BankNotificationService
            getContext().getSharedPreferences("SMSReaderPrefs", 0)
                .edit()
                .putString("server_url", serverUrl)
                .apply();
            
            // Update the service if running
            BankNotificationService.setServerUrl(serverUrl);
            
            JSObject result = new JSObject();
            result.put("success", true);
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error saving config", e);
            call.reject("Error saving config: " + e.getMessage());
        }
    }
    
    /**
     * Get the saved configuration
     */
    @PluginMethod
    public void getConfig(PluginCall call) {
        try {
            String serverUrl = getContext().getSharedPreferences("SMSReaderPrefs", 0)
                .getString("server_url", "https://sevenapp.onrender.com");
            
            JSObject result = new JSObject();
            result.put("serverUrl", serverUrl);
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error getting config", e);
            call.reject("Error getting config: " + e.getMessage());
        }
    }
    
    /**
     * Request to restart the notification listener service
     * This can help if the service stops responding
     */
    @PluginMethod
    public void restartService(PluginCall call) {
        try {
            if (!isNotificationServiceEnabled()) {
                call.reject("Notification access not granted");
                return;
            }
            
            // Toggle the notification listener to restart it
            // This is a workaround since we can't directly restart the service
            String packageName = getContext().getPackageName();
            String componentName = packageName + "/" + packageName + ".BankNotificationService";
            
            // Disable
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                // For Android N and above, we need to use a different approach
                // The service will automatically restart when notification access is toggled
            }
            
            Log.i(TAG, "Service restart requested");
            
            JSObject result = new JSObject();
            result.put("success", true);
            result.put("message", "Service restart requested. Please toggle notification access off and on if issues persist.");
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error restarting service", e);
            call.reject("Error restarting service: " + e.getMessage());
        }
    }
    
    /**
     * Send a test notification to verify the webhook
     */
    @PluginMethod
    public void sendTestTransaction(PluginCall call) {
        try {
            double amount = call.getDouble("amount", 100000.0);
            String content = call.getString("content", "NAP 7TY001");
            String serverUrl = call.getString("serverUrl");
            
            if (serverUrl == null || serverUrl.isEmpty()) {
                serverUrl = getContext().getSharedPreferences("BankReaderConfig", 0)
                    .getString("serverUrl", "https://sevenapp.onrender.com");
            }
            
            // Send test transaction in background
            final String finalServerUrl = serverUrl;
            final double finalAmount = amount;
            final String finalContent = content;
            
            new Thread(() -> {
                try {
                    String result = BankNotificationService.sendTransactionToServer(
                        getContext(),
                        "credit",
                        (long) finalAmount,
                        finalContent,
                        "TEST_" + System.currentTimeMillis(),
                        "ACB",
                        "test_notification"
                    );
                    Log.i(TAG, "Test transaction result: " + result);
                } catch (Exception e) {
                    Log.e(TAG, "Error sending test transaction", e);
                }
            }).start();
            
            JSObject result = new JSObject();
            result.put("success", true);
            result.put("message", "Test transaction sent");
            call.resolve(result);
        } catch (Exception e) {
            Log.e(TAG, "Error sending test transaction", e);
            call.reject("Error sending test transaction: " + e.getMessage());
        }
    }
    
    /**
     * Check if the notification listener service is enabled for this app
     */
    private boolean isNotificationServiceEnabled() {
        String pkgName = getContext().getPackageName();
        String flat = Settings.Secure.getString(getContext().getContentResolver(), 
            "enabled_notification_listeners");
        
        if (!TextUtils.isEmpty(flat)) {
            String[] names = flat.split(":");
            for (String name : names) {
                ComponentName cn = ComponentName.unflattenFromString(name);
                if (cn != null) {
                    if (TextUtils.equals(pkgName, cn.getPackageName())) {
                        return true;
                    }
                }
            }
        }
        return false;
    }
}
