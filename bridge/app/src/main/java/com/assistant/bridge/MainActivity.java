package com.assistant.bridge;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
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
     * Test Python connection
     */
    private void testPythonConnection() {
        Log.d(TAG, "Testing Python connection");
        
        new Thread(() -> {
            try {
                // In a real implementation, this would test the connection
                // to the Python server running in Termux
                
                runOnUiThread(() -> {
                    Toast.makeText(this, "Python connection test: OK", Toast.LENGTH_SHORT).show();
                });
                
            } catch (Exception e) {
                runOnUiThread(() -> {
                    Toast.makeText(this, "Connection failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                });
            }
        }).start();
    }
    
    /**
     * Open accessibility settings
     */
    private void openAccessibilitySettings() {
        try {
            Intent intent = new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS);
            startActivity(intent);
        } catch (Exception e) {
            Log.e(TAG, "Error opening accessibility settings", e);
        }
    }
    
    /**
     * Check if accessibility service is running
     */
    private boolean isAccessibilityServiceRunning() {
        AccessibilityManager am = (AccessibilityManager) getSystemService(ACCESSIBILITY_SERVICE);
        if (am != null) {
            for (AccessibilityManager.AccessibilityServiceInfo service : am.getEnabledAccessibilityServiceList(0)) {
                if (service.getId().contains(AccessibilityBridgeService.class.getName())) {
                    return true;
                }
            }
        }
        return false;
    }
}
