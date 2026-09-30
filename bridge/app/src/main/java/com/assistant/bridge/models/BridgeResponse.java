package com.assistant.bridge.models;

import java.io.Serializable;
import java.util.HashMap;
import java.util.Map;

/**
 * Bridge Response Model
 * Represents a response from the bridge
 */
public class BridgeResponse implements Serializable {
    
    public enum Status {
        SUCCESS,
        FAILURE,
        ERROR,
        TIMEOUT,
        CANCELLED
    }
    
    private String requestId;
    private String responseId;
    private Status status;
    private String message;
    private Map<String, Object> data;
    private long timestamp;
    private long processingTime;
    
    public BridgeResponse() {
        this.responseId = java.util.UUID.randomUUID().toString();
        this.timestamp = System.currentTimeMillis();
        this.data = new HashMap<>();
        this.status = Status.SUCCESS;
    }
    
    public BridgeResponse(String requestId) {
        this();
        this.requestId = requestId;
    }
    
    // Getters and Setters
    
    public String getRequestId() {
        return requestId;
    }
    
    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }
    
    public String getResponseId() {
        return responseId;
    }
    
    public void setResponseId(String responseId) {
        this.responseId = responseId;
    }
    
    public Status getStatus() {
        return status;
    }
    
    public void setStatus(Status status) {
        this.status = status;
    }
    
    public String getMessage() {
        return message;
    }
    
    public void setMessage(String message) {
        this.message = message;
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
    
    public long getProcessingTime() {
        return processingTime;
    }
    
    public void setProcessingTime(long processingTime) {
        this.processingTime = processingTime;
    }
    
    @Override
    public String toString() {
        return "BridgeResponse{" +
                "requestId='" + requestId + '\'' +
                ", responseId='" + responseId + '\'' +
                ", status=" + status +
                ", message='" + message + '\'' +
                ", data=" + data +
                ", timestamp=" + timestamp +
                ", processingTime=" + processingTime +
                '}';
    }
    
    /**
     * Check if response is successful
     */
    public boolean isSuccess() {
        return status == Status.SUCCESS;
    }
    
    /**
     * Check if response is an error
     */
    public boolean isError() {
        return status == Status.ERROR || status == Status.FAILURE;
    }
    
    /**
     * Convert to JSON string
     */
    public String toJson() {
        try {
            org.json.JSONObject json = new org.json.JSONObject();
            json.put("requestId", requestId);
            json.put("responseId", responseId);
            json.put("status", status.name());
            json.put("message", message);
            json.put("timestamp", timestamp);
            json.put("processingTime", processingTime);
            
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
    public static BridgeResponse fromJson(String jsonString) {
        try {
            org.json.JSONObject json = new org.json.JSONObject(jsonString);
            
            BridgeResponse response = new BridgeResponse();
            response.setRequestId(json.optString("requestId", ""));
            response.setResponseId(json.optString("responseId", ""));
            response.setStatus(Status.valueOf(json.optString("status", "SUCCESS")));
            response.setMessage(json.optString("message", ""));
            response.setTimestamp(json.optLong("timestamp", System.currentTimeMillis()));
            response.setProcessingTime(json.optLong("processingTime", 0));
            
            // Parse data
            org.json.JSONObject dataJson = json.optJSONObject("data");
            if (dataJson != null) {
                Map<String, Object> data = new HashMap<>();
                for (String key : dataJson.keySet()) {
                    data.put(key, dataJson.getString(key));
                }
                response.setData(data);
            }
            
            return response;
        } catch (Exception e) {
            return new BridgeResponse();
        }
    }
    
    /**
     * Create success response
     */
    public static BridgeResponse createSuccess(String requestId, String message) {
        BridgeResponse response = new BridgeResponse(requestId);
        response.setStatus(Status.SUCCESS);
        response.setMessage(message);
        return response;
    }
    
    /**
     * Create error response
     */
    public static BridgeResponse createError(String requestId, String errorMessage) {
        BridgeResponse response = new BridgeResponse(requestId);
        response.setStatus(Status.ERROR);
        response.setMessage(errorMessage);
        return response;
    }
    
    /**
     * Create failure response
     */
    public static BridgeResponse createFailure(String requestId, String message) {
        BridgeResponse response = new BridgeResponse(requestId);
        response.setStatus(Status.FAILURE);
        response.setMessage(message);
        return response;
    }
}
