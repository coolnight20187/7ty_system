package com.ty7.smsreader;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import androidx.core.app.NotificationCompat;

/**
 * Background Service - Giữ app SMS Reader chạy ngầm liên tục
 * 
 * Service này sẽ:
 * - Hiển thị notification cố định để Android không kill app
 * - Giữ WakeLock để tránh bị suspend
 * - Tự động restart nếu bị kill
 */
public class BackgroundService extends Service {
    
    private static final String TAG = "BackgroundService";
    private static final String CHANNEL_ID = "sms_reader_background";
    private static final int NOTIFICATION_ID = 7777;
    
    private PowerManager.WakeLock wakeLock;
    private static BackgroundService instance;
    
    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        Log.i(TAG, "BackgroundService created");
        
        // Acquire WakeLock
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager != null) {
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK, 
                "SMSReader::BackgroundWakeLock"
            );
            wakeLock.acquire();
            Log.i(TAG, "WakeLock acquired");
        }
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "BackgroundService started");
        
        createNotificationChannel();
        startForeground(NOTIFICATION_ID, createNotification());
        
        // Return START_STICKY để service tự restart nếu bị kill
        return START_STICKY;
    }
    
    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        
        // Release WakeLock
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
            Log.i(TAG, "WakeLock released");
        }
        
        Log.i(TAG, "BackgroundService destroyed - attempting restart");
        
        // Tự động restart service
        Intent restartIntent = new Intent(this, BackgroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(restartIntent);
        } else {
            startService(restartIntent);
        }
    }
    
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
    
    public static boolean isRunning() {
        return instance != null;
    }
    
    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "SMS Reader Background",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Đọc thông báo ngân hàng tự động");
            channel.setShowBadge(false);
            channel.setSound(null, null);
            
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
    
    private Notification createNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        
        return new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("7TY SMS Reader")
            .setContentText("Đang theo dõi thông báo ngân hàng...")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build();
    }
    
    /**
     * Update notification với thông tin mới
     */
    public void updateNotification(String message) {
        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            Intent notificationIntent = new Intent(this, MainActivity.class);
            PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notificationIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
            );
            
            Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("7TY SMS Reader")
                .setContentText(message)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setCategory(NotificationCompat.CATEGORY_SERVICE)
                .build();
            
            manager.notify(NOTIFICATION_ID, notification);
        }
    }
}
