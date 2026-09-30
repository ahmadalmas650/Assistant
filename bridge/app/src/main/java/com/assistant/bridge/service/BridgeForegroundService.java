package com.assistant.bridge.service;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import com.assistant.bridge.MainActivity;
import com.assistant.bridge.R;
import com.assistant.bridge.utils.BridgeConstants;

/**
 * Bridge Foreground Service
 * Runs in foreground to maintain connection with Python brain
 */
public class BridgeForegroundService extends Service {
    
    private static final String TAG = "JARVIS_Foreground";
    private static final String CHANNEL_ID = "jarvis_bridge_channel";
    private static final int NOTIFICATION_ID = 1001;
    
    private static BridgeForegroundService instance;
    private boolean isRunning = false;
    
    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        
        Log.d(TAG, "Foreground Service created");
        
        // Create notification channel
        createNotificationChannel();
        
        // Start as foreground service
        startForeground(NOTIFICATION_ID, createNotification());
        
        isRunning = true;
    }
    
    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "Foreground Service started");
        
        // Handle start command
        if (intent != null) {
            String action = intent.getAction();
            if (action != null) {
                handleAction(action, intent);
            }
        }
        
        return START_STICKY;
    }
    
    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        isRunning = false;
        
        Log.d(TAG, "Foreground Service destroyed");
    }
    
    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
    
    /**
     * Create notification channel
     */
    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "JARVIS Bridge",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("JARVIS Bridge Service");
            channel.setShowBadge(false);
            channel.setLockscreenVisibility(Notification.VISIBILITY_SECRET);
            
            NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }
    
    /**
     * Create notification for foreground service
     */
    private Notification createNotification() {
        // Create intent for notification click
        Intent notificationIntent = new Intent(this, MainActivity.class);
        notificationIntent.setAction(Intent.ACTION_MAIN);
        notificationIntent.addCategory(Intent.CATEGORY_LAUNCHER);
        notificationIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        
        PendingIntent pendingIntent = PendingIntent.getActivity(
            this, 0, notificationIntent, 
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? 
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT : 
                PendingIntent.FLAG_UPDATE_CURRENT
        );
        
        // Build notification
        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(BridgeConstants.APP_NAME)
            .setContentText("Bridge service is running")
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setAutoCancel(false);
        
        return builder.build();
    }
    
    /**
     * Handle action from intent
     */
    private void handleAction(String action, Intent intent) {
        Log.d(TAG, "Handling action: " + action);
        
        switch (action) {
            case BridgeConstants.PYTHON_SERVICE:
                // Start Python connection
                startPythonConnection();
                break;
                
            case "STOP_SERVICE":
                stopSelf();
                break;
                
            default:
                Log.w(TAG, "Unknown action: " + action);
        }
    }
    
    /**
     * Start Python connection
     */
    private void startPythonConnection() {
        Log.d(TAG, "Starting Python connection");
        
        // In a real implementation, this would connect to the Python server
        // running in Termux
        
        // For now, just log
        new Thread(() -> {
            try {
                // Simulate connection
                Log.d(TAG, "Python connection thread started");
                
                // This would connect to localhost:8000 where Python server runs
                // and maintain the connection
                
                while (isRunning) {
                    Thread.sleep(5000);
                    Log.d(TAG, "Python connection heartbeat");
                }
                
            } catch (InterruptedException e) {
                Log.e(TAG, "Python connection interrupted", e);
            }
        }).start();
    }
    
    /**
     * Update notification
     */
    public void updateNotification(String title, String text) {
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(text)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build();
        
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify(NOTIFICATION_ID, notification);
        }
    }
    
    // Public methods
    
    /**
     * Get instance
     */
    public static BridgeForegroundService getInstance() {
        return instance;
    }
    
    /**
     * Check if service is running
     */
    public static boolean isRunning() {
        return instance != null && instance.isRunning;
    }
    
    /**
     * Start the foreground service
     */
    public static void startService(Context context) {
        Intent intent = new Intent(context, BridgeForegroundService.class);
        intent.setAction(BridgeConstants.PYTHON_SERVICE);
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }
    
    /**
     * Stop the foreground service
     */
    public static void stopService(Context context) {
        Intent intent = new Intent(context, BridgeForegroundService.class);
        intent.setAction("STOP_SERVICE");
        context.stopService(intent);
    }
}
