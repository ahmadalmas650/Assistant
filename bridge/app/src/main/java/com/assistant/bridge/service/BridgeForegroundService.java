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
 * Runs the localhost JSON-RPC server (LocalJsonRpcServer on
 * BridgeConstants.BRIDGE_PORT) that the Python brain in Termux connects
 * to, and dispatches every method to the accessibility service, the
 * launcher controller or the voice controller. No simulated work.
 */
public class BridgeForegroundService extends Service {

    private static final String TAG = "JARVIS_Foreground";
    private static final String CHANNEL_ID = "jarvis_bridge_channel";
    private static final int NOTIFICATION_ID = 1001;

    private static BridgeForegroundService instance;
    private boolean isRunning = false;
    private LocalJsonRpcServer rpcServer;
    private VoiceController voice;

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;

        Log.d(TAG, "Foreground Service created");

        createNotificationChannel();
        try {
            startForeground(NOTIFICATION_ID, createNotification());
        } catch (Exception e) {
            // Android 14+ requires RECORD_AUDIO to be granted before
            // starting a microphone-type foreground service.
            Log.e(TAG, "startForeground failed (mic permission not granted?): "
                    + e.getMessage());
            stopSelf();
            return;
        }

        voice = new VoiceController(this);
        rpcServer = new LocalJsonRpcServer(BridgeConstants.BRIDGE_PORT,
                (method, paramsJson) -> dispatch(method, paramsJson));
        rpcServer.start();
        isRunning = true;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.d(TAG, "Foreground Service started");

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
        isRunning = false;
        if (rpcServer != null) {
            rpcServer.stop();
            rpcServer = null;
        }
        if (voice != null) {
            voice.shutdown();
            voice = null;
        }
        instance = null;
        Log.d(TAG, "Foreground Service destroyed");
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // ------------------------------------------------------------------
    // Method dispatcher (single source of truth for the RPC surface)
    // ------------------------------------------------------------------

    private String dispatch(String method, String params) {
        switch (method) {
            case "ping":
                return "{\"ok\":true,\"service\":\"jarvis-bridge\",\"version\":"
                        + json(BridgeConstants.APP_VERSION_NAME) + "}";

            case "get_screen_text":
                return accessibilityOrError("read the screen");

            case "get_all_nodes": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                return svc.collectNodesJson((int) num(params, "max_nodes", 200));
            }

            case "get_foreground_app": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                return "{\"ok\":true,\"package\":" + json(svc.getCurrentPackageName())
                        + ",\"window_title\":" + json(svc.getCurrentWindowTitle()) + "}";
            }

            case "click_node": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                String text = str(params, "text");
                String nodeId = str(params, "node_id");
                int x = (int) num(params, "x", -1);
                int y = (int) num(params, "y", -1);
                if (text != null && !text.isEmpty()) {
                    return svc.clickByText(text);
                }
                if (nodeId != null && !nodeId.isEmpty()) {
                    return svc.clickById(nodeId);
                }
                if (x >= 0 && y >= 0) {
                    return svc.clickAt(x, y);
                }
                return errJson("click_node needs text, node_id or x/y");
            }

            case "input_text": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                String text = str(params, "text");
                return svc.inputTextIntoField(text);
            }

            case "swipe": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                return svc.swipe((int) num(params, "start_x", 0),
                        (int) num(params, "start_y", 0),
                        (int) num(params, "end_x", 0),
                        (int) num(params, "end_y", 0),
                        (int) num(params, "duration_ms", 300));
            }

            case "press_back":
            case "press_home":
            case "press_recents": {
                AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
                if (svc == null) {
                    return errJson("accessibility service not connected");
                }
                if ("press_back".equals(method)) {
                    return svc.pressBack();
                }
                return "press_home".equals(method) ? svc.pressHome() : svc.pressRecents();
            }

            case "launch_app":
                return LauncherController.launchByPackage(this, str(params, "package"));

            case "launch_app_by_name":
                return LauncherController.launchByName(this,
                        AccessibilityBridgeService.getInstance(),
                        str(params, "name"));

            case "is_app_installed":
                return LauncherController.isInstalled(this, str(params, "package"));

            case "notification_info":
                // Honest limitation: not implemented; reading notifications
                // is handled by the accessibility event stream instead.
                return errJson("notification_info is not implemented; use get_screen_text");

            // Voice session control (see VoiceController for the state machine)
            case "stt_start_wake":
                return voice.startWake(str(params, "wake_word"), str(params, "language"));
            case "stt_start_command":
                return voice.startCommand(str(params, "language"));
            case "stt_status":
                return voice.status();
            case "stt_set_text":
                return voice.setText(str(params, "text"));
            case "stt_finish":
                return voice.finish();
            case "stt_cancel":
                return voice.cancel();
            case "speech_to_text":
                return voice.recognizeOnce(str(params, "language"),
                        num(params, "timeout_s", 10.0));
            case "listen_wake_word":
                return voice.listenWakeBlocking(str(params, "wake_word"),
                        num(params, "timeout_s", 30.0));

            // Streaming TTS
            case "tts_speak":
                return voice.speak(str(params, "text"), str(params, "language"));
            case "tts_stop":
                return voice.ttsStop();
            case "tts_status":
                return voice.ttsStatus();

            default:
                return errJson("unknown method: " + method);
        }
    }

    private String accessibilityOrError(String what) {
        AccessibilityBridgeService svc = AccessibilityBridgeService.getInstance();
        if (svc == null) {
            return errJson("accessibility service not connected; cannot " + what);
        }
        return svc.collectVisibleText();
    }

    private static String errJson(String message) {
        return "{\"ok\":false,\"error\":" + json(message) + "}";
    }

    // ------------------------------------------------------------------
    // Minimal JSON parameter extraction (paramsJson is a flat object)
    // ------------------------------------------------------------------

    private static String json(String s) {
        return VoiceController.json(s);
    }

    private static String str(String params, String key) {
        if (params == null) {
            return null;
        }
        String needle = "\"" + key + "\"";
        int idx = params.indexOf(needle);
        if (idx < 0) {
            return null;
        }
        idx = params.indexOf(':', idx + needle.length());
        if (idx < 0) {
            return null;
        }
        int i = idx + 1;
        while (i < params.length() && Character.isWhitespace(params.charAt(i))) {
            i++;
        }
        if (i >= params.length() || params.charAt(i) != '"') {
            return null;
        }
        i++;
        StringBuilder sb = new StringBuilder();
        while (i < params.length()) {
            char c = params.charAt(i);
            if (c == '\\' && i + 1 < params.length()) {
                char next = params.charAt(i + 1);
                sb.append(next == 'n' ? '\n' : next == 'r' ? '\r' : next);
                i += 2;
                continue;
            }
            if (c == '"') {
                break;
            }
            sb.append(c);
            i++;
        }
        return sb.toString();
    }

    private static double num(String params, String key, double fallback) {
        String s = str(params, key);
        if (s == null || s.isEmpty()) {
            return fallback;
        }
        try {
            return Double.parseDouble(s.trim());
        } catch (NumberFormatException e) {
            return fallback;
        }
    }

    // ------------------------------------------------------------------
    // Notification plumbing
    // ------------------------------------------------------------------

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

    private Notification createNotification() {
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

    private void handleAction(String action, Intent intent) {
        Log.d(TAG, "Handling action: " + action);

        switch (action) {
            case BridgeConstants.PYTHON_SERVICE:
                if (rpcServer != null && !rpcServer.isRunning()) {
                    rpcServer.start();
                }
                break;

            case "STOP_SERVICE":
                stopSelf();
                break;

            default:
                Log.w(TAG, "Unknown action: " + action);
        }
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

    public static BridgeForegroundService getInstance() {
        return instance;
    }

    public static boolean isRunning() {
        return instance != null && instance.isRunning;
    }

    public static void startService(Context context) {
        Intent intent = new Intent(context, BridgeForegroundService.class);
        intent.setAction(BridgeConstants.PYTHON_SERVICE);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    public static void stopService(Context context) {
        Intent intent = new Intent(context, BridgeForegroundService.class);
        intent.setAction("STOP_SERVICE");
        context.stopService(intent);
    }
}
