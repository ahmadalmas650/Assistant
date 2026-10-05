package com.assistant.bridge;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.view.accessibility.AccessibilityManager;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.assistant.bridge.service.AccessibilityBridgeService;
import com.assistant.bridge.service.BridgeForegroundService;
import com.assistant.bridge.utils.BridgeConstants;

/**
 * Main Activity for JARVIS Bridge
 * Provides UI for bridge configuration and status
 */
public class MainActivity extends AppCompatActivity {
    
    private static final String TAG = "JARVIS_MainActivity";
    
    private TextView statusText;
    private Button startBridgeButton;
    private Button stopBridgeButton;
    private Button checkAccessibilityButton;
    private Button testConnectionButton;
    
    private boolean isBound = false;
    
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        
        Log.d(TAG, "MainActivity created");
        
        // Initialize views
        initializeViews();
        
        // Runtime permissions required for voice (STT/TTS) and the
        // foreground-service notification on Android 13+
        ensureRuntimePermissions();
        
        // Update status
        updateStatus();
    }
    
    @Override
    protected void onResume() {
        super.onResume();
        updateStatus();
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (isBound) {
            isBound = false;
        }
    }
    
    /**
     * Initialize views
     */
    private void initializeViews() {
        statusText = findViewById(R.id.status_text);
        startBridgeButton = findViewById(R.id.start_bridge_button);
        stopBridgeButton = findViewById(R.id.stop_bridge_button);
        checkAccessibilityButton = findViewById(R.id.check_accessibility_button);
        testConnectionButton = findViewById(R.id.test_connection_button);
        
        // Set click listeners
        startBridgeButton.setOnClickListener(v -> startBridgeService());
        stopBridgeButton.setOnClickListener(v -> stopBridgeService());
        checkAccessibilityButton.setOnClickListener(v -> checkAccessibilityService());
        testConnectionButton.setOnClickListener(v -> testPythonConnection());
    }
    
    /**
     * Update status display
     */
    private void updateStatus() {
        StringBuilder sb = new StringBuilder();
        
        // Check bridge service
        boolean bridgeRunning = BridgeForegroundService.isRunning();
        sb.append("Bridge Service: ").append(bridgeRunning ? "Running" : "Stopped").append("\n");
        
        // Check accessibility service
        boolean accessibilityEnabled = AccessibilityBridgeService.isServiceEnabled(this);
        sb.append("Accessibility: ").append(accessibilityEnabled ? "Enabled" : "Disabled").append("\n");
        
        // Check Termux
        boolean hasTermux = BridgeConstants.hasTermux();
        sb.append("Termux: ").append(hasTermux ? "Installed" : "Not installed").append("\n");
        
        // Check Shizuku
        boolean hasShizuku = BridgeConstants.hasShizuku();
        sb.append("Shizuku: ").append(hasShizuku ? "Available" : "Not available").append("\n");
        
        // Device info
        sb.append("\nDevice: ").append(BridgeConstants.getDeviceManufacturer()).append(" ");
        sb.append(BridgeConstants.getDeviceModel()).append("\n");
        sb.append("Android: ").append(BridgeConstants.getAndroidVersion());
        
        statusText.setText(sb.toString());
        
        // Update button states
        startBridgeButton.setEnabled(!bridgeRunning);
        stopBridgeButton.setEnabled(bridgeRunning);
    }
    
    /**
     * Start bridge service
     */
    private void startBridgeService() {
        Log.d(TAG, "Starting bridge service");
        
        try {
            BridgeForegroundService.startService(this);
            updateStatus();
            Toast.makeText(this, "Bridge service started", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Error starting bridge service", e);
            Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }
    
    /**
     * Stop bridge service
     */
    private void stopBridgeService() {
        Log.d(TAG, "Stopping bridge service");
        
        try {
            BridgeForegroundService.stopService(this);
            updateStatus();
            Toast.makeText(this, "Bridge service stopped", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Error stopping bridge service", e);
            Toast.makeText(this, "Error: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }
    
    /**
     * Check accessibility service
     */
    private void checkAccessibilityService() {
        Log.d(TAG, "Checking accessibility service");
        
        boolean enabled = AccessibilityBridgeService.isServiceEnabled(this);
        
        if (enabled) {
            Toast.makeText(this, "Accessibility service is enabled", Toast.LENGTH_SHORT).show();
        } else {
            // Open accessibility settings
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            startActivity(intent);
            Toast.makeText(this, "Please enable JARVIS Accessibility Service", Toast.LENGTH_LONG).show();
        }
    }
    
    /**
     * Request the runtime permissions the bridge needs: microphone for
     * STT/wake word, notifications for the foreground service on 13+.
     */
    private void ensureRuntimePermissions() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED
                || (Build.VERSION.SDK_INT >= 33
                        && ContextCompat.checkSelfPermission(this,
                                "android.permission.POST_NOTIFICATIONS")
                                != PackageManager.PERMISSION_GRANTED)) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.RECORD_AUDIO,
                            "android.permission.POST_NOTIFICATIONS"},
                    1001);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions,
                                           int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 1001) {
            boolean micGranted = false;
            for (int i = 0; i < permissions.length; i++) {
                if (Manifest.permission.RECORD_AUDIO.equals(permissions[i])
                        && i < grantResults.length && grantResults[i] == PackageManager.PERMISSION_GRANTED) {
                    micGranted = true;
                }
            }
            if (!micGranted) {
                Toast.makeText(this, "Microphone permission is required for voice control",
                        Toast.LENGTH_LONG).show();
            }
        }
    }

    /**
     * Test Python connection
     */
    private void testPythonConnection() {
        Log.d(TAG, "Testing Python connection");

        new Thread(() -> {
            // Real check: connect to the bridge's own JSON-RPC server and
            // send a ping; the Python brain in Termux talks to this same port.
            String result;
            try (java.net.Socket socket = new java.net.Socket()) {
                socket.connect(new java.net.InetSocketAddress("127.0.0.1",
                        com.assistant.bridge.utils.BridgeConstants.BRIDGE_PORT), 2000);
                socket.setSoTimeout(2000);
                socket.getOutputStream().write(
                        "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\",\"params\":{}}\n"
                                .getBytes(java.nio.charset.StandardCharsets.UTF_8));
                socket.getOutputStream().flush();
                byte[] buf = new byte[1024];
                int n = socket.getInputStream().read(buf);
                String response = n > 0 ? new String(buf, 0, n, java.nio.charset.StandardCharsets.UTF_8).trim() : "";
                result = response.contains("\"ok\":true")
                        ? "Bridge RPC server reachable: " + response
                        : "Unexpected RPC response: " + response;
            } catch (Exception e) {
                result = "Connection failed: " + e.getMessage();
            }
            final String message = result;
            runOnUiThread(() ->
                    Toast.makeText(this, message, Toast.LENGTH_LONG).show());
        }).start();
    }
}

