package com.assistant.bridge.service;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;

import com.assistant.bridge.utils.BridgeConstants;

/**
 * Bridge Broadcast Receiver
 * Handles broadcast intents for the bridge
 */
public class BridgeBroadcastReceiver extends BroadcastReceiver {
    
    private static final String TAG = "JARVIS_Broadcast";
    
    @Override
    public void onReceive(Context context, Intent intent) {
        try {
            String action = intent.getAction();
            if (action == null) return;
            
            Log.d(TAG, "Received broadcast: " + action);
            
            // Handle different actions
            switch (action) {
                case BridgeConstants.BRIDGE_ACTION:
                    handleBridgeAction(context, intent);
                    break;
                    
                case BridgeConstants.BRIDGE_COMMAND:
                    handleBridgeCommand(context, intent);
                    break;
                    
                default:
                    Log.w(TAG, "Unknown broadcast action: " + action);
            }
            
        } catch (Exception e) {
            Log.e(TAG, "Error handling broadcast", e);
        }
    }
    
    /**
     * Handle bridge action
     */
    private void handleBridgeAction(Context context, Intent intent) {
        Bundle extras = intent.getExtras();
        if (extras != null) {
            String command = extras.getString("command", "");
            String data = extras.getString("data", "");
            
            Log.d(TAG, "Bridge action - command: " + command + ", data: " + data);
            
            // Forward to foreground service
            Intent serviceIntent = new Intent(context, BridgeForegroundService.class);
            serviceIntent.setAction(BridgeConstants.BRIDGE_COMMAND);
            serviceIntent.putExtras(extras);
            
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent);
            } else {
                context.startService(serviceIntent);
            }
        }
    }
    
    /**
     * Handle bridge command
     */
    private void handleBridgeCommand(Context context, Intent intent) {
        Bundle extras = intent.getExtras();
        if (extras != null) {
            String command = extras.getString("command", "");
            String data = extras.getString("data", "");
            
            Log.d(TAG, "Bridge command - command: " + command + ", data: " + data);
            
            // Process command
            processCommand(context, command, data);
        }
    }
    
    /**
     * Process command
     */
    private void processCommand(Context context, String command, String data) {
        try {
            // Parse command and data
            // In a real implementation, this would communicate with Python
            
            Log.d(TAG, "Processing command: " + command);
            
            // Send response
            sendResponse(context, command, "Command received", true);
            
        } catch (Exception e) {
            Log.e(TAG, "Error processing command", e);
            sendResponse(context, command, "Error: " + e.getMessage(), false);
        }
    }
    
    /**
     * Send response back to sender
     */
    private void sendResponse(Context context, String requestId, String message, boolean success) {
        Intent responseIntent = new Intent(BridgeConstants.BRIDGE_RESPONSE);
        responseIntent.putExtra("request_id", requestId);
        responseIntent.putExtra("message", message);
        responseIntent.putExtra("success", success);
        responseIntent.putExtra("timestamp", System.currentTimeMillis());
        
        context.sendBroadcast(responseIntent);
    }
}
