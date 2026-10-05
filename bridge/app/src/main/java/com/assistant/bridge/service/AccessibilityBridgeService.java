package com.assistant.bridge.service;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.AccessibilityServiceInfo;
import android.accessibilityservice.GestureDescription;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.WindowManager;

import androidx.annotation.RequiresApi;

import com.assistant.bridge.MainActivity;
import com.assistant.bridge.utils.BridgeConstants;

import java.util.ArrayList;
import java.util.List;

/**
 * Accessibility Bridge Service
 * Provides accessibility features for JARVIS
 */
public class AccessibilityBridgeService extends AccessibilityService {
    
    private static final String TAG = "JARVIS_Accessibility";
    
    private static AccessibilityBridgeService instance;
    
    // Callbacks for events
    private static List<AccessibilityEventCallback> eventCallbacks = new ArrayList<>();
    private static List<NodeInfoCallback> nodeInfoCallbacks = new ArrayList<>();
    
    // For overlay
    private WindowManager windowManager;
    private WindowManager.LayoutParams overlayParams;
    
    // For gesture detection
    private boolean isListeningForWakeWord = false;
    private String currentWakeWord = "jarvis";
    
    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        
        Log.d(TAG, "Accessibility Service created");
        
        // Initialize window manager for overlays
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
    }
    
    @Override
    public void onDestroy() {
        super.onDestroy();
        instance = null;
        Log.d(TAG, "Accessibility Service destroyed");
    }
    
    @Override
    public void onServiceConnected() {
        super.onServiceConnected();
        Log.d(TAG, "Accessibility Service connected");
        
        // Configure service
        AccessibilityServiceInfo info = new AccessibilityServiceInfo();
        info.eventTypes = AccessibilityEvent.TYPE_ALL_MASK;
        info.feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC;
        info.notificationTimeout = 100;
        info.flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS |
                    AccessibilityServiceInfo.FLAG_REQUEST_TOUCH_EXPLORATION_MODE |
                    AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS;
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            info.settingsActivityName = MainActivity.class.getName();
        }
        
        setServiceInfo(info);
    }
    
    @Override
    public boolean onUnbind(Intent intent) {
        Log.d(TAG, "Accessibility Service unbound");
        return super.onUnbind(intent);
    }
    
    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        try {
            if (event == null) return;
            
            int eventType = event.getEventType();
            
            // Log the event
            logAccessibilityEvent(event);
            
            // Notify callbacks
            for (AccessibilityEventCallback callback : eventCallbacks) {
                try {
                    callback.onAccessibilityEvent(event);
                } catch (Exception e) {
                    Log.e(TAG, "Error in accessibility event callback", e);
                }
            }
            
            // Handle specific events
            switch (eventType) {
                case AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED:
                    handleWindowStateChanged(event);
                    break;
                    
                case AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED:
                    handleTextChanged(event);
                    break;
                    
                case AccessibilityEvent.TYPE_VIEW_CLICKED:
                    handleViewClicked(event);
                    break;
                    
                case AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED:
                    handleWindowContentChanged(event);
                    break;
            }
            
            // Check for wake word
            if (isListeningForWakeWord) {
                checkForWakeWord(event);
            }
            
        } catch (Exception e) {
            Log.e(TAG, "Error handling accessibility event", e);
        }
    }
    
    @Override
    public void onInterrupt() {
        Log.d(TAG, "Accessibility Service interrupted");
    }
    
    /**
     * Log accessibility event
     */
    private void logAccessibilityEvent(AccessibilityEvent event) {
        StringBuilder sb = new StringBuilder();
        sb.append("Event: ").append(event.getEventType());
        sb.append(", Package: ").append(event.getPackageName());
        sb.append(", Class: ").append(event.getClassName());
        sb.append(", Text: ").append(event.getText());
        sb.append(", Source: ").append(event.getSource());
        
        Log.d(TAG, sb.toString());
    }
    
    /**
     * Handle window state changed event
     */
    private void handleWindowStateChanged(AccessibilityEvent event) {
        String packageName = event.getPackageName() != null ? event.getPackageName().toString() : "";
        String className = event.getClassName() != null ? event.getClassName().toString() : "";
        
        Log.d(TAG, "Window state changed: " + packageName + " / " + className);
        
        // Notify callbacks
        for (AccessibilityEventCallback callback : eventCallbacks) {
            try {
                callback.onWindowStateChanged(packageName, className);
            } catch (Exception e) {
                Log.e(TAG, "Error in window state callback", e);
            }
        }
    }
    
    /**
     * Handle text changed event
     */
    private void handleTextChanged(AccessibilityEvent event) {
        List<CharSequence> text = event.getText();
        if (text != null && !text.isEmpty()) {
            StringBuilder sb = new StringBuilder();
            for (CharSequence cs : text) {
                sb.append(cs);
            }
            String fullText = sb.toString();
            
            Log.d(TAG, "Text changed: " + fullText);
            
            // Check for wake word in text
            if (isListeningForWakeWord && fullText.toLowerCase().contains(currentWakeWord.toLowerCase())) {
                handleWakeWordDetected(fullText);
            }
        }
    }
    
    /**
     * Handle view clicked event
     */
    private void handleViewClicked(AccessibilityEvent event) {
        AccessibilityNodeInfo source = event.getSource();
        if (source != null) {
            String viewId = source.getViewIdResourceName();
            String text = source.getText() != null ? source.getText().toString() : "";
            String className = source.getClassName() != null ? source.getClassName().toString() : "";
            
            Log.d(TAG, "View clicked: " + viewId + " (" + className + ") - " + text);
            
            // Notify callbacks
            for (AccessibilityEventCallback callback : eventCallbacks) {
                try {
                    callback.onViewClicked(viewId, text, className);
                } catch (Exception e) {
                    Log.e(TAG, "Error in view clicked callback", e);
                }
            }
        }
    }
    
    /**
     * Handle window content changed event
     */
    private void handleWindowContentChanged(AccessibilityEvent event) {
        AccessibilityNodeInfo rootNode = getRootInActiveWindow();
        if (rootNode != null) {
            try {
                // Traverse the node tree
                traverseNodeTree(rootNode, 0);
                
                // Notify callbacks
                for (NodeInfoCallback callback : nodeInfoCallbacks) {
                    try {
                        callback.onWindowContentChanged(rootNode);
                    } catch (Exception e) {
                        Log.e(TAG, "Error in window content callback", e);
                    }
                }
            } finally {
                rootNode.recycle();
            }
        }
    }
    
    /**
     * Traverse the accessibility node tree
     */
    private void traverseNodeTree(AccessibilityNodeInfo node, int depth) {
        if (node == null) return;
        
        try {
            String indent = "  ".repeat(depth);
            StringBuilder sb = new StringBuilder();
            sb.append(indent);
            
            if (node.getClassName() != null) {
                sb.append(node.getClassName());
            }
            
            if (node.getViewIdResourceName() != null) {
                sb.append(" [").append(node.getViewIdResourceName()).append("]");
            }
            
            if (node.getText() != null) {
                sb.append(" = ").append(node.getText());
            }
            
            if (node.isClickable()) {
                sb.append(" [CLICKABLE]");
            }
            if (node.isFocusable()) {
                sb.append(" [FOCUSABLE]");
            }
            if (node.isEnabled()) {
                sb.append(" [ENABLED]");
            }
            if (!node.isVisibleToUser()) {
                sb.append(" [HIDDEN]");
            }
            
            Log.d(TAG, sb.toString());
            
            // Recurse into children
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) {
                    traverseNodeTree(child, depth + 1);
                    child.recycle();
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error traversing node tree", e);
        }
    }
    
    /**
     * Check for wake word in event
     */
    private void checkForWakeWord(AccessibilityEvent event) {
        List<CharSequence> text = event.getText();
        if (text != null) {
            for (CharSequence cs : text) {
                if (cs != null && cs.toString().toLowerCase().contains(currentWakeWord.toLowerCase())) {
                    handleWakeWordDetected(cs.toString());
                    break;
                }
            }
        }
    }
    
    /**
     * Handle wake word detection
     */
    private void handleWakeWordDetected(String text) {
        Log.d(TAG, "Wake word detected: " + text);
        
        // Notify callbacks
        for (AccessibilityEventCallback callback : eventCallbacks) {
            try {
                callback.onWakeWordDetected(currentWakeWord, text);
            } catch (Exception e) {
                Log.e(TAG, "Error in wake word callback", e);
            }
        }
    }
    
    // Public methods
    
    /**
     * Get instance
     */
    public static AccessibilityBridgeService getInstance() {
        return instance;
    }
    
    /**
     * Check if service is enabled
     */
    public static boolean isServiceEnabled(Context context) {
        try {
            int accessibilityEnabled = android.provider.Settings.Secure.getInt(
                context.getContentResolver(),
                android.provider.Settings.Secure.ACCESSIBILITY_ENABLED
            );
            
            if (accessibilityEnabled == 1) {
                String services = android.provider.Settings.Secure.getString(
                    context.getContentResolver(),
                    android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
                );
                
                if (services != null) {
                    return services.toLowerCase().contains(
                        AccessibilityBridgeService.class.getName().toLowerCase()
                    );
                }
            }
            return false;
        } catch (Exception e) {
            return false;
        }
    }
    
    /**
     * Start listening for wake word
     */
    public void startListeningForWakeWord(String wakeWord) {
        this.currentWakeWord = wakeWord;
        this.isListeningForWakeWord = true;
        Log.d(TAG, "Started listening for wake word: " + wakeWord);
    }
    
    /**
     * Stop listening for wake word
     */
    public void stopListeningForWakeWord() {
        this.isListeningForWakeWord = false;
        Log.d(TAG, "Stopped listening for wake word");
    }
    
    /**
     * Get root node in active window
     */
    public AccessibilityNodeInfo getCurrentRootNode() {
        return getRootInActiveWindow();
    }
    
    /**
     * Find node by text
     */
    public AccessibilityNodeInfo findNodeByText(String text) {
        return findNodeByText(text, getRootInActiveWindow());
    }
    
    /**
     * Find node by text recursively
     */
    private AccessibilityNodeInfo findNodeByText(String text, AccessibilityNodeInfo root) {
        if (root == null || text == null) return null;
        
        try {
            if (root.getText() != null && root.getText().toString().contains(text)) {
                return root;
            }
            
            for (int i = 0; i < root.getChildCount(); i++) {
                AccessibilityNodeInfo child = root.getChild(i);
                if (child != null) {
                    AccessibilityNodeInfo result = findNodeByText(text, child);
                    if (result != null) {
                        child.recycle();
                        return result;
                    }
                    child.recycle();
                }
            }
            
            return null;
        } catch (Exception e) {
            Log.e(TAG, "Error finding node by text", e);
            return null;
        }
    }
    
    /**
     * Find node by view ID
     */
    public AccessibilityNodeInfo findNodeById(String viewId) {
        return findNodeById(viewId, getRootInActiveWindow());
    }
    
    /**
     * Find node by view ID recursively
     */
    private AccessibilityNodeInfo findNodeById(String viewId, AccessibilityNodeInfo root) {
        if (root == null || viewId == null) return null;
        
        try {
            String nodeId = root.getViewIdResourceName();
            if (nodeId != null && nodeId.equals(viewId)) {
                return root;
            }
            
            for (int i = 0; i < root.getChildCount(); i++) {
                AccessibilityNodeInfo child = root.getChild(i);
                if (child != null) {
                    AccessibilityNodeInfo result = findNodeById(viewId, child);
                    if (result != null) {
                        child.recycle();
                        return result;
                    }
                    child.recycle();
                }
            }
            
            return null;
        } catch (Exception e) {
            Log.e(TAG, "Error finding node by ID", e);
            return null;
        }
    }
    
    /**
     * Perform click on node
     */
    public boolean performClick(AccessibilityNodeInfo node) {
        if (node == null) return false;
        
        try {
            if (node.isClickable()) {
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK);
            } else {
                // Try to find clickable parent
                AccessibilityNodeInfo parent = node.getParent();
                while (parent != null) {
                    if (parent.isClickable()) {
                        return parent.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                    }
                    AccessibilityNodeInfo grandParent = parent.getParent();
                    parent.recycle();
                    parent = grandParent;
                }
            }
            return false;
        } catch (Exception e) {
            Log.e(TAG, "Error performing click", e);
            return false;
        }
    }
    
    /**
     * Perform click at coordinates
     */
    @RequiresApi(api = Build.VERSION_CODES.N)
    public boolean performClick(int x, int y) {
        try {
            Path clickPath = new Path();
            clickPath.moveTo(x, y);
            
            GestureDescription.Builder gestureBuilder = new GestureDescription.Builder();
            gestureBuilder.addStroke(new GestureDescription.StrokeDescription(
                clickPath, 0, 50
            ));
            
            GestureDescription gesture = gestureBuilder.build();
            return dispatchGesture(gesture, null, null);
        } catch (Exception e) {
            Log.e(TAG, "Error performing click at coordinates", e);
            return false;
        }
    }
    
    /**
     * Perform scroll
     */
    public boolean performScroll(AccessibilityNodeInfo node, int direction) {
        if (node == null) return false;
        
        try {
            if (node.isScrollable()) {
                return node.performAction(direction);
            }
            return false;
        } catch (Exception e) {
            Log.e(TAG, "Error performing scroll", e);
            return false;
        }
    }
    
    /**
     * Set text in node
     */
    public boolean setText(AccessibilityNodeInfo node, String text) {
        if (node == null || text == null) return false;
        
        try {
            Bundle arguments = new Bundle();
            arguments.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text);
            return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments);
        } catch (Exception e) {
            Log.e(TAG, "Error setting text", e);
            return false;
        }
    }
    
    /**
     * Get text from node
     */
    public String getText(AccessibilityNodeInfo node) {
        if (node == null) return "";
        
        try {
            CharSequence text = node.getText();
            return text != null ? text.toString() : "";
        } catch (Exception e) {
            Log.e(TAG, "Error getting text", e);
            return "";
        }
    }
    
    /**
     * Get current package name
     */
    public String getCurrentPackageName() {
        AccessibilityNodeInfo rootNode = getRootInActiveWindow();
        if (rootNode != null) {
            try {
                return rootNode.getPackageName() != null ? rootNode.getPackageName().toString() : "";
            } finally {
                rootNode.recycle();
            }
        }
        return "";
    }
    
    /**
     * Get current window title
     */
    public String getCurrentWindowTitle() {
        AccessibilityNodeInfo rootNode = getRootInActiveWindow();
        if (rootNode != null) {
            try {
                AccessibilityNodeInfo titleNode = findNodeById("android:id/action_bar_title", rootNode);
                if (titleNode != null) {
                    try {
                        return getText(titleNode);
                    } finally {
                        titleNode.recycle();
                    }
                }
                return "";
            } finally {
                rootNode.recycle();
            }
        }
        return "";
    }
    
    /**
     * Collect all visible text from the active window as a live screen
     * reading (accessibility nodes, no screenshots, no OCR).
     */
    public String collectVisibleText() {
        AccessibilityNodeInfo rootNode = getRootInActiveWindow();
        if (rootNode == null) {
            return "{\"ok\":false,\"error\":\"no active window\"}";
        }
        StringBuilder sb = new StringBuilder();
        try {
            collectText(rootNode, sb);
        } finally {
            rootNode.recycle();
        }
        return "{\"ok\":true,\"text\":" + json(sb.toString()) + "}";
    }

    private void collectText(AccessibilityNodeInfo node, StringBuilder sb) {
        if (node == null) {
            return;
        }
        try {
            CharSequence text = node.getText();
            if (text != null && text.length() > 0) {
                if (sb.length() > 0) {
                    sb.append('\n');
                }
                sb.append(text.toString());
            }
            CharSequence desc = node.getContentDescription();
            if (desc != null && desc.length() > 0) {
                if (sb.length() > 0) {
                    sb.append('\n');
                }
                sb.append(desc.toString());
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) {
                    collectText(child, sb);
                    child.recycle();
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error collecting text", e);
        }
    }

    /**
     * Collect visible nodes as JSON (bounded by maxNodes so a huge tree
     * never floods the RPC channel).
     */
    public String collectNodesJson(int maxNodes) {
        AccessibilityNodeInfo rootNode = getRootInActiveWindow();
        if (rootNode == null) {
            return "{\"ok\":false,\"error\":\"no active window\"}";
        }
        int limit = maxNodes <= 0 ? 200 : Math.min(maxNodes, 1000);
        StringBuilder sb = new StringBuilder("[");
        try {
            appendNodeJson(rootNode, sb, limit, new int[]{0});
        } finally {
            rootNode.recycle();
        }
        sb.append(']');
        return "{\"ok\":true,\"nodes\":" + sb.toString() + "}";
    }

    private void appendNodeJson(AccessibilityNodeInfo node, StringBuilder sb, int limit, int[] count) {
        if (node == null || count[0] >= limit) {
            return;
        }
        count[0]++;
        if (count[0] > 1) {
            sb.append(',');
        }
        sb.append("{\"text\":").append(json(getText(node)))
          .append(",\"id\":").append(json(node.getViewIdResourceName()))
          .append(",\"class\":").append(json(node.getClassName() == null ? "" : node.getClassName().toString()))
          .append(",\"bounds\":\"").append(node.getBoundsInScreen().toString()).append('"')
          .append(",\"clickable\":").append(node.isClickable())
          .append(",\"scrollable\":").append(node.isScrollable())
          .append(",\"editable\":").append(node.isEditable())
          .append('}');
        for (int i = 0; i < node.getChildCount() && count[0] < limit; i++) {
            AccessibilityNodeInfo child = node.getChild(i);
            if (child != null) {
                appendNodeJson(child, sb, limit, count);
                child.recycle();
            }
        }
    }

    /**
     * Click the first node whose text or content description contains the
     * given text. Returns a JSON result; never throws.
     */
    public String clickByText(String text) {
        if (text == null || text.isEmpty()) {
            return "{\"ok\":false,\"error\":\"no text given\"}";
        }
        AccessibilityNodeInfo node = findNodeByText(text);
        if (node == null) {
            return "{\"ok\":false,\"error\":\"no node found with text: " + text + "\"}";
        }
        boolean clicked = performClick(node);
        node.recycle();
        return clicked ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"node not clickable: " + text + "\"}";
    }

    /**
     * Click the node with the given view id resource name.
     */
    public String clickById(String viewId) {
        if (viewId == null || viewId.isEmpty()) {
            return "{\"ok\":false,\"error\":\"no view id given\"}";
        }
        AccessibilityNodeInfo node = findNodeById(viewId);
        if (node == null) {
            return "{\"ok\":false,\"error\":\"no node found with id: " + viewId + "\"}";
        }
        boolean clicked = performClick(node);
        node.recycle();
        return clicked ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"node not clickable: " + viewId + "\"}";
    }

    /**
     * Click at absolute screen coordinates using a gesture.
     */
    public String clickAt(int x, int y) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) {
            return "{\"ok\":false,\"error\":\"gesture clicks need Android 7.0+\"}";
        }
        return performClick(x, y)
                ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"gesture dispatch failed\"}";
    }

    /**
     * Swipe gesture between two screen points.
     */
    public String swipe(int startX, int startY, int endX, int endY, int durationMs) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) {
            return "{\"ok\":false,\"error\":\"gestures need Android 7.0+\"}";
        }
        try {
            Path path = new Path();
            path.moveTo(startX, startY);
            path.lineTo(endX, endY);
            GestureDescription.Builder builder = new GestureDescription.Builder();
            builder.addStroke(new GestureDescription.StrokeDescription(
                    path, 0, Math.max(50, durationMs)));
            boolean dispatched = dispatchGesture(builder.build(), null, null);
            return dispatched ? "{\"ok\":true}"
                    : "{\"ok\":false,\"error\":\"gesture dispatch failed\"}";
        } catch (Exception e) {
            Log.e(TAG, "Error swiping", e);
            return "{\"ok\":false,\"error\":\"" + e.getMessage() + "\"}";
        }
    }

    /**
     * Global navigation actions.
     */
    public String pressBack() {
        return performGlobalAction(GLOBAL_ACTION_BACK)
                ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"back failed\"}";
    }

    public String pressHome() {
        return performGlobalAction(GLOBAL_ACTION_HOME)
                ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"home failed\"}";
    }

    public String pressRecents() {
        return performGlobalAction(GLOBAL_ACTION_RECENTS)
                ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"recents failed\"}";
    }

    /**
     * Type text into the focused or first editable field on screen.
     */
    public String inputTextIntoField(String text) {
        if (text == null || text.isEmpty()) {
            return "{\"ok\":false,\"error\":\"no text given\"}";
        }
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) {
            return "{\"ok\":false,\"error\":\"no active window\"}";
        }
        try {
            AccessibilityNodeInfo field = findEditableField(root);
            if (field == null) {
                return "{\"ok\":false,\"error\":\"no editable field on screen\"}";
            }
            boolean set = setText(field, text);
            field.performAction(AccessibilityNodeInfo.ACTION_FOCUS);
            field.recycle();
            return set ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"could not set text\"}";
        } finally {
            root.recycle();
        }
    }

    private AccessibilityNodeInfo findEditableField(AccessibilityNodeInfo root) {
        if (root.isEditable()) {
            return root;
        }
        for (int i = 0; i < root.getChildCount(); i++) {
            AccessibilityNodeInfo child = root.getChild(i);
            if (child == null) {
                continue;
            }
            AccessibilityNodeInfo found = findEditableField(child);
            if (found != null) {
                if (found != child) {
                    child.recycle();
                }
                return found;
            }
            child.recycle();
        }
        return null;
    }

    /**
     * Get the default launcher package (used by the human-style app
     * launching flow; never used to launch apps directly).
     */
    public String getLauncherPackage() {
        try {
            Intent home = new Intent(Intent.ACTION_MAIN);
            home.addCategory(Intent.CATEGORY_HOME);
            PackageManager pm = getPackageManager();
            ResolveInfo info = pm.resolveActivity(home, PackageManager.MATCH_DEFAULT_ONLY);
            if (info != null && info.activityInfo != null) {
                return info.activityInfo.packageName;
            }
        } catch (Exception e) {
            Log.e(TAG, "Error resolving launcher", e);
        }
        return "";
    }

    /**
     * JSON string escaper shared across bridge service classes.
     */
    public static String json(String s) {
        if (s == null) {
            return "\"\"";
        }
        StringBuilder sb = new StringBuilder(s.length() + 8);
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n");  break;
                case '\r': sb.append("\\r");  break;
                case '\t': sb.append("\\t");  break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
        return sb.toString();
    }

    // Callback interfaces
    
    public interface AccessibilityEventCallback {
        void onAccessibilityEvent(AccessibilityEvent event);
        void onWindowStateChanged(String packageName, String className);
        void onViewClicked(String viewId, String text, String className);
        void onWakeWordDetected(String wakeWord, String text);
    }
    
    public interface NodeInfoCallback {
        void onWindowContentChanged(AccessibilityNodeInfo rootNode);
    }
    
    // Callback registration
    
    public static void registerEventCallback(AccessibilityEventCallback callback) {
        if (!eventCallbacks.contains(callback)) {
            eventCallbacks.add(callback);
        }
    }
    
    public static void unregisterEventCallback(AccessibilityEventCallback callback) {
        eventCallbacks.remove(callback);
    }
    
    public static void registerNodeInfoCallback(NodeInfoCallback callback) {
        if (!nodeInfoCallbacks.contains(callback)) {
            nodeInfoCallbacks.add(callback);
        }
    }
    
    public static void unregisterNodeInfoCallback(NodeInfoCallback callback) {
        nodeInfoCallbacks.remove(callback);
    }
}

