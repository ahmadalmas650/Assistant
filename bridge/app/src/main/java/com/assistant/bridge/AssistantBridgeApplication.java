package com.assistant.bridge;

import android.app.Application;
import android.content.Context;
import android.util.Log;

import com.assistant.bridge.service.BridgeForegroundService;
import com.assistant.bridge.utils.BridgeConstants;

/**
 * JARVIS Bridge Application
 * Main application class for the Android Bridge
 */
public class AssistantBridgeApplication extends Application {
    
    private static final String TAG = "JARVIS_Bridge_App";
    
    private static Context appContext;
    private static AssistantBridgeApplication instance;
    
    @Override
    public void onCreate() {
        super.onCreate();
        appContext = getApplicationContext();
        instance = this;
        
        Log.d(TAG, "JARVIS Bridge Application started");
        
        // Initialize bridge components
        initializeBridge();
    }
    
    private void initializeBridge() {
        Log.d(TAG, "Initializing bridge components");
        
        // Initialize constants
        BridgeConstants.initialize(this);
        
        // Start foreground service if needed
        BridgeForegroundService.startService(this);
    }
    
    @Override
    public void onTerminate() {
        super.onTerminate();
        Log.d(TAG, "JARVIS Bridge Application terminated");
    }
    
    /**
     * Get application context
     */
    public static Context getAppContext() {
        return appContext;
    }
    
    /**
     * Get application instance
     */
    public static AssistantBridgeApplication getInstance() {
        return instance;
    }
    
    /**
     * Check if application is running in Termux environment
     */
    public static boolean isRunningInTermux() {
        try {
            // Check for Termux package
            return appContext != null && 
                   appContext.getPackageManager().getPackageInfo("com.termux", 0) != null;
        } catch (Exception e) {
            return false;
        }
    }
}
