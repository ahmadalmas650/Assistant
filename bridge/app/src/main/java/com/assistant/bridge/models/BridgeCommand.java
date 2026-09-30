package com.assistant.bridge.models;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

/**
 * Bridge Command Model
 * Represents a command sent to/from the bridge
 */
public class BridgeCommand implements Serializable {
    
    public enum CommandType {
        EXECUTE,
        QUERY,
        RESPONSE,
        EVENT,
        ERROR,
        STATUS
    }
    
    public enum Priority {
        LOW,
        NORMAL,
        HIGH,
        CRITICAL
    }
    
    private String id;
    private CommandType type;
    private Priority priority;
    private String action;
    private Map<String, Object> data;
    private long timestamp;
    private String source;
    private String destination;
    private boolean requiresResponse;
    private String responseId;
    
    public BridgeCommand() {
        this.id = java.util.UUID.randomUUID().toString();
        this.timestamp = System.currentTimeMillis();
        this.data = new HashMap<>();
        this.priority = Priority.NORMAL;
        this.type = CommandType.EXECUTE;
        this.requiresResponse = true;
    }
    
    public BridgeCommand(String action) {
        this();
        this.action = action;
    }
    
    // Getters and Setters
    
    public String getId() {
        return id;
    }
    
    public void setId(String id) {
        this.id = id;
    }
    
    public CommandType getType() {
        return type;
    }
    
    public void setType(CommandType type) {
        this.type = type;
    }
    
    public Priority getPriority() {
        return priority;
    }
    
    public void setPriority(Priority priority) {
        this.priority = priority;
    }
    
    public String getAction() {
        return action;
    }
    
    public void setAction(String action) {
        this.action = action;
    }
    
    public Map<String, Object> getData() {
        return data;
    }
    
    public void setData(Map<String, Object> data) {
        this.data = data;
    }
    
    public Object getData(String key) {
        return data != null ? data.get(key) : null;
    }
    
    public void putData(String key, Object value) {
        if (data == null) {
            data = new HashMap<>();
        }
        data.put(key, value);
    }
    
    public long getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(long timestamp) {
        this.timestamp = timestamp;
    }
    
    public String getSource() {
        return source;
    }
    
    public void setSource(String source) {
        this.source = source;
    }
    
    public String getDestination() {
        return destination;
    }
    
    public void setDestination(String destination) {
        this.destination = destination;
    }
    
    public boolean isRequiresResponse() {
        return requiresResponse;
    }
    
    public void setRequiresResponse(boolean requiresResponse) {
        this.requiresResponse = requiresResponse;
    }
    
    public String getResponseId() {
        return responseId;
    }
    
    public void setResponseId(String responseId) {
        this.responseId = responseId;
    }
    
    @Override
    public String toString() {
        return "BridgeCommand{" +
                "id='" + id + '\'' +
                ", type=" + type +
                ", priority=" + priority +
                ", action='" + action + '\'' +
                ", data=" + data +
                ", timestamp=" + timestamp +
                ", source='" + source + '\'' +
                ", destination='" + destination + '\'' +
                ", requiresResponse=" + requiresResponse +
                '}';
    }
    
    /**
     * Create a response command
     */
    public BridgeCommand createResponse() {
        BridgeCommand response = new BridgeCommand();
        response.setType(CommandType.RESPONSE);
        response.setResponseId(this.id);
        response.setDestination(this.source);
        response.setSource(this.destination);
        return response;
    }
    
    /**
     * Create an error command
     */
    public BridgeCommand createError(String errorMessage) {
        BridgeCommand error = new BridgeCommand();
        error.setType(CommandType.ERROR);
        error.setResponseId(this.id);
        error.setDestination(this.source);
        error.setSource(this.destination);
        error.putData("error", errorMessage);
        return error;
    }
    
    /**
     * Convert to JSON string
     */
    public String toJson() {
        try {
            org.json.JSONObject json = new org.json.JSONObject();
            json.put("id", id);
            json.put("type", type.name());
            json.put("priority", priority.name());
            json.put("action", action);
            json.put("timestamp", timestamp);
            json.put("source", source);
            json.put("destination", destination);
            json.put("requiresResponse", requiresResponse);
            json.put("responseId", responseId);
            
            if (data != null) {
                org.json.JSONObject dataJson = new org.json.JSONObject();
                for (Map.Entry<String, Object> entry : data.entrySet()) {
                    dataJson.put(entry.getKey(), entry.getValue() != null ? entry.getValue().toString() : "");
                }
                json.put("data", dataJson);
            }
            
            return json.toString();
        } catch (Exception e) {
            return "{}";
        }
    }
    
    /**
     * Create from JSON string
     */
    public static BridgeCommand fromJson(String jsonString) {
        try {
            org.json.JSONObject json = new org.json.JSONObject(jsonString);
            
            BridgeCommand command = new BridgeCommand();
            command.setId(json.optString("id", ""));
            command.setType(CommandType.valueOf(json.optString("type", "EXECUTE")));
            command.setPriority(Priority.valueOf(json.optString("priority", "NORMAL")));
            command.setAction(json.optString("action", ""));
            command.setTimestamp(json.optLong("timestamp", System.currentTimeMillis()));
            command.setSource(json.optString("source", ""));
            command.setDestination(json.optString("destination", ""));
            command.setRequiresResponse(json.optBoolean("requiresResponse", true));
            command.setResponseId(json.optString("responseId", ""));
            
            // Parse data
            org.json.JSONObject dataJson = json.optJSONObject("data");
            if (dataJson != null) {
                Map<String, Object> data = new HashMap<>();
                for (String key : dataJson.keySet()) {
                    data.put(key, dataJson.getString(key));
                }
                command.setData(data);
            }
            
            return command;
        } catch (Exception e) {
            return new BridgeCommand();
        }
    }
}
