package com.assistant.bridge.utils;

import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Bridge Constants
 * Contains all constants and configuration for the bridge
 */
public class BridgeConstants {
    
    private static final String TAG = "JARVIS_Constants";
    
    // Application info
    public static final String APP_NAME = "JARVIS Bridge";
    public static final String APP_PACKAGE = "com.assistant.bridge";
    public static final int APP_VERSION_CODE = 1;
    public static final String APP_VERSION_NAME = "1.0.0";
    
    // Communication
    public static final String BRIDGE_ACTION = "com.assistant.bridge.ACTION";
    public static final String BRIDGE_COMMAND = "com.assistant.bridge.COMMAND";
    public static final String BRIDGE_RESPONSE = "com.assistant.bridge.RESPONSE";
    public static final String BRIDGE_ERROR = "com.assistant.bridge.ERROR";
    public static final String BRIDGE_LOG = "com.assistant.bridge.LOG";
    
    // Termux integration
    public static final String TERMUX_PACKAGE = "com.termux";
    public static final String TERMUX_API_PACKAGE = "com.termux.api";
    public static final String TERMUX_FILE_PROVIDER = "com.termux.fileprovider";
    public static final String BRIDGE_FILE_PROVIDER = "com.assistant.bridge.fileprovider";
    
    // Python integration
    public static final String PYTHON_SERVICE = "com.assistant.bridge.PYTHON_SERVICE";
    public static final String PYTHON_BRAIN_PATH = "/data/data/com.termux/files/home/Assistant/brain/main.py";
    public static final String PYTHON_SCRIPT_DIR = "/data/data/com.termux/files/home/Assistant/scripts/";
    
    // Ports
    public static final int BRIDGE_PORT = 8080;
    public static final int PYTHON_PORT = 8000;
    public static final int WEB_SOCKET_PORT = 8081;
    
    // Timeouts
    public static final long COMMAND_TIMEOUT = 30000; // 30 seconds
    public static final long CONNECTION_TIMEOUT = 10000; // 10 seconds
    public static final long EXECUTION_TIMEOUT = 300000; // 5 minutes
    
    // File paths
    public static final String BRIDGE_DIR = "/data/data/com.assistant.bridge/";
    public static final String TEMP_DIR = BRIDGE_DIR + "temp/";
    public static final String CACHE_DIR = BRIDGE_DIR + "cache/";
    public static final String LOG_DIR = BRIDGE_DIR + "logs/";
    public static final String CONFIG_DIR = BRIDGE_DIR + "config/";
    
    // Log file
    public static final String MAIN_LOG_FILE = LOG_DIR + "bridge.log";
    public static final String ERROR_LOG_FILE = LOG_DIR + "errors.log";
    
    // Configuration file
    public static final String CONFIG_FILE = CONFIG_DIR + "config.json";
    
    // Allowed apps for integration
    public static final List<String> ALLOWED_APPS = Arrays.asList(
        "com.android.chrome",
        "com.google.android.youtube",
        "com.openai.chatgpt",
        "com.deepseek.app",
        "ai.x.grok",
        "com.nexstreaming.app.kinemasterfree",
        "org.telegram.messenger",
        "com.whatsapp",
        "com.google.android.gm",
        "com.android.email"
    );
    
    // Dangerous apps (require confirmation)
    public static final List<String> DANGEROUS_APPS = Arrays.asList(
        "com.android.settings",
        "com.android.phone",
        "com.android.contacts",
        "com.android.providers.contacts"
    );
    
    // Sensitive permissions
    public static final List<String> SENSITIVE_PERMISSIONS = Arrays.asList(
        "android.permission.READ_CONTACTS",
        "android.permission.READ_SMS",
        "android.permission.READ_CALL_LOG",
        "android.permission.READ_CALENDAR",
        "android.permission.WRITE_CONTACTS",
        "android.permission.SEND_SMS",
        "android.permission.CALL_PHONE"
    );
    
    // Device info
    private static Context appContext;
    private static String deviceModel;
    private static String deviceManufacturer;
    private static String androidVersion;
    private static int sdkVersion;
    private static boolean isRooted = false;
    private static boolean hasShizuku = false;
    private static boolean hasTermux = false;
    
    /**
     * Initialize constants with context
     */
    public static void initialize(Context context) {
        appContext = context.getApplicationContext();
        
        // Get device info
        deviceModel = Build.MODEL;
        deviceManufacturer = Build.MANUFACTURER;
        androidVersion = Build.VERSION.RELEASE;
        sdkVersion = Build.VERSION.SDK_INT;
        
        // Check for root
        isRooted = checkRootAccess();
        
        // Check for Shizuku
        hasShizuku = checkPackageInstalled("moe.shizuku.privileged.api");
        
        // Check for Termux
        hasTermux = checkPackageInstalled(TERMUX_PACKAGE);
        
        Log.d(TAG, "Device: " + deviceManufacturer + " " + deviceModel);
        Log.d(TAG, "Android: " + androidVersion + " (SDK " + sdkVersion + ")");
        Log.d(TAG, "Root: " + isRooted + ", Shizuku: " + hasShizuku + ", Termux: " + hasTermux);
    }
    
    /**
     * Check if device has root access
     */
    private static boolean checkRootAccess() {
        try {
            // Check for su binary
            return new java.io.File("/system/bin/su").exists() ||
                   new java.io.File("/system/xbin/su").exists();
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Check if a package is installed
     */
    public static boolean checkPackageInstalled(String packageName) {
        try {
            return appContext != null && 
                   appContext.getPackageManager().getPackageInfo(packageName, 0) != null;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }
    
    /**
     * Check if an app is in the allowed list
     */
    public static boolean isAppAllowed(String packageName) {
        return ALLOWED_APPS.contains(packageName);
    }
    
    /**
     * Check if an app is dangerous
     */
    public static boolean isAppDangerous(String packageName) {
        return DANGEROUS_APPS.contains(packageName);
    }
    
    /**
     * Check if a permission is sensitive
     */
    public static boolean isPermissionSensitive(String permission) {
        return SENSITIVE_PERMISSIONS.contains(permission);
    }
    
    // Getters
    
    public static Context getAppContext() {
        return appContext;
    }
    
    public static String getDeviceModel() {
        return deviceModel;
    }
    
    public static String getDeviceManufacturer() {
        return deviceManufacturer;
    }
    
    public static String getAndroidVersion() {
        return androidVersion;
    }
    
    public static int getSdkVersion() {
        return sdkVersion;
    }
    
    public static boolean isRooted() {
        return isRooted;
    }
    
    public static boolean hasShizuku() {
        return hasShizuku;
    }
    
    public static boolean hasTermux() {
        return hasTermux;
    }
    
    /**
     * Get the bridge directory path
     */
    public static String getBridgeDirectory() {
        return BRIDGE_DIR;
    }
    
    /**
     * Get the temp directory path
     */
    public static String getTempDirectory() {
        return TEMP_DIR;
    }
    
    /**
     * Get the cache directory path
     */
    public static String getCacheDirectory() {
        return CACHE_DIR;
    }
    
    /**
     * Get the log directory path
     */
    public static String getLogDirectory() {
        return LOG_DIR;
    }
    
    /**
     * Get the config directory path
     */
    public static String getConfigDirectory() {
        return CONFIG_DIR;
    }
}
