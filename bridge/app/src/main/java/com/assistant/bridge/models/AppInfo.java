package com.assistant.bridge.models;

import android.graphics.drawable.Drawable;

import java.io.Serializable;

/**
 * App Information Model
 * Contains information about installed applications
 */
public class AppInfo implements Serializable {
    
    private String packageName;
    private String appName;
    private String versionName;
    private int versionCode;
    private Drawable icon;
    private boolean isSystemApp;
    private boolean isEnabled;
    private String permissions;
    private String activities;
    
    public AppInfo() {
    }
    
    public AppInfo(String packageName, String appName, String versionName, 
                  int versionCode, Drawable icon, boolean isSystemApp, 
                  boolean isEnabled) {
        this.packageName = packageName;
        this.appName = appName;
        this.versionName = versionName;
        this.versionCode = versionCode;
        this.icon = icon;
        this.isSystemApp = isSystemApp;
        this.isEnabled = isEnabled;
        this.permissions = "";
        this.activities = "";
    }
    
    // Getters and Setters
    
    public String getPackageName() {
        return packageName;
    }
    
    public void setPackageName(String packageName) {
        this.packageName = packageName;
    }
    
    public String getAppName() {
        return appName;
    }
    
    public void setAppName(String appName) {
        this.appName = appName;
    }
    
    public String getVersionName() {
        return versionName;
    }
    
    public void setVersionName(String versionName) {
        this.versionName = versionName;
    }
    
    public int getVersionCode() {
        return versionCode;
    }
    
    public void setVersionCode(int versionCode) {
        this.versionCode = versionCode;
    }
    
    public Drawable getIcon() {
        return icon;
    }
    
    public void setIcon(Drawable icon) {
        this.icon = icon;
    }
    
    public boolean isSystemApp() {
        return isSystemApp;
    }
    
    public void setSystemApp(boolean systemApp) {
        isSystemApp = systemApp;
    }
    
    public boolean isEnabled() {
        return isEnabled;
    }
    
    public void setEnabled(boolean enabled) {
        isEnabled = enabled;
    }
    
    public String getPermissions() {
        return permissions;
    }
    
    public void setPermissions(String permissions) {
        this.permissions = permissions;
    }
    
    public String getActivities() {
        return activities;
    }
    
    public void setActivities(String activities) {
        this.activities = activities;
    }
    
    @Override
    public String toString() {
        return "AppInfo{" +
                "packageName='" + packageName + '\'' +
                ", appName='" + appName + '\'' +
                ", versionName='" + versionName + '\'' +
                ", versionCode=" + versionCode +
                ", isSystemApp=" + isSystemApp +
                ", isEnabled=" + isEnabled +
                '}';
    }
    
    /**
     * Check if app can be used for a specific capability
     */
    public boolean hasCapability(String capability) {
        if (capability == null) return false;
        
        switch (capability.toLowerCase()) {
            case "browser":
            case "web":
                return packageName != null && 
                       (packageName.contains("chrome") || 
                        packageName.contains("browser") ||
                        packageName.contains("firefox") ||
                        packageName.contains("edge"));
                        
            case "video":
            case "youtube":
                return packageName != null && 
                       (packageName.contains("youtube") ||
                        packageName.contains("video"));
                        
            case "chat":
            case "messaging":
                return packageName != null && 
                       (packageName.contains("whatsapp") ||
                        packageName.contains("telegram") ||
                        packageName.contains("messenger") ||
                        packageName.contains("chat"));
                        
            case "ai":
            case "assistant":
                return packageName != null && 
                       (packageName.contains("chatgpt") ||
                        packageName.contains("deepseek") ||
                        packageName.contains("grok") ||
                        packageName.contains("assistant"));
                        
            case "editor":
            case "photo":
                return packageName != null && 
                       (packageName.contains("kinemaster") ||
                        packageName.contains("photo") ||
                        packageName.contains("editor") ||
                        packageName.contains("picsart") ||
                        packageName.contains("snapseed"));
                        
            default:
                return false;
        }
    }
}
