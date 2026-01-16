package com.ty7.smsreader;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    
    private static final String TAG = "MainActivity";
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(SMSReaderPlugin.class);
        registerPlugin(NotificationReaderPlugin.class);
        super.onCreate(savedInstanceState);
        
        // Khởi động BackgroundService để app chạy ngầm
        startBackgroundService();
        
        // Yêu cầu tắt tối ưu pin
        requestIgnoreBatteryOptimization();
    }
    
    @Override
    public void onResume() {
        super.onResume();
        // Đảm bảo BackgroundService luôn chạy
        if (!BackgroundService.isRunning()) {
            startBackgroundService();
        }
    }
    
    private void startBackgroundService() {
        try {
            Intent serviceIntent = new Intent(this, BackgroundService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(serviceIntent);
            } else {
                startService(serviceIntent);
            }
            Log.i(TAG, "BackgroundService started");
        } catch (Exception e) {
            Log.e(TAG, "Failed to start BackgroundService: " + e.getMessage());
        }
    }
    
    private void requestIgnoreBatteryOptimization() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
                String packageName = getPackageName();
                
                if (pm != null && !pm.isIgnoringBatteryOptimizations(packageName)) {
                    Intent intent = new Intent();
                    intent.setAction(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + packageName));
                    startActivity(intent);
                    Log.i(TAG, "Requested ignore battery optimization");
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to request battery optimization: " + e.getMessage());
        }
    }
}
