package com.assistant.bridge.service;

import android.util.Log;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Lightweight localhost JSON-RPC 2.0 server.
 *
 * Zero external dependencies: plain blocking sockets on 127.0.0.1 only
 * (never exposed to the network). The Python brain in Termux connects to
 * this port and exchanges newline-delimited JSON-RPC 2.0 messages.
 *
 * Wire format (one JSON object per line):
 *   request:  {"jsonrpc":"2.0","id":1,"method":"ping","params":{}}
 *   response: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}
 *
 * Methods are resolved via a single handler callback supplied by the
 * foreground service, so no service internals are hard-coded here.
 */
public final class LocalJsonRpcServer {

    private static final String TAG = "LocalJsonRpcServer";
    private static final int MAX_LINE_BYTES = 4 * 1024 * 1024; // 4 MB safety cap

    /** Handler for one JSON-RPC method. Returns the result object. */
    public interface MethodHandler {
        Object handle(String method, String paramsJson) throws Exception;
    }

    private final int port;
    private final MethodHandler handler;
    private final AtomicBoolean running = new AtomicBoolean(false);
    private ServerSocket serverSocket;
    private ExecutorService executor;

    public LocalJsonRpcServer(int port, MethodHandler handler) {
        this.port = port;
        this.handler = handler;
    }

    /** Start serving on the loopback interface. Idempotent. */
    public synchronized void start() {
        if (running.get()) {
            return;
        }
        try {
            InetAddress loopback = InetAddress.getByName("127.0.0.1");
            serverSocket = new ServerSocket(port, 4, loopback);
            serverSocket.setReuseAddress(true);
            running.set(true);
            executor = Executors.newCachedThreadPool();
            Thread acceptor = new Thread(this::acceptLoop, "rpc-acceptor");
            acceptor.setDaemon(true);
            acceptor.start();
            Log.i(TAG, "JSON-RPC server listening on 127.0.0.1:" + port);
        } catch (IOException e) {
            Log.e(TAG, "failed to start server on port " + port, e);
            running.set(false);
        }
    }

    /** Stop the server and release resources. Idempotent. */
    public synchronized void stop() {
        running.set(false);
        try {
            if (serverSocket != null && !serverSocket.isClosed()) {
                serverSocket.close();
            }
        } catch (IOException ignored) {
            // closing is best-effort
        }
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        Log.i(TAG, "JSON-RPC server stopped");
    }

    public boolean isRunning() {
        return running.get();
    }

    public int getPort() {
        return port;
    }

    private void acceptLoop() {
        while (running.get()) {
            try {
                Socket client = serverSocket.accept();
                if (executor != null) {
                    executor.submit(() -> serveClient(client));
                } else {
                    closeQuietly(client);
                }
            } catch (IOException e) {
                if (running.get()) {
                    Log.w(TAG, "accept failed: " + e.getMessage());
                }
            }
        }
    }

    private void serveClient(Socket client) {
        try (Socket socket = client) {
            socket.setTcpNoDelay(true);
            BufferedReader reader = new BufferedReader(
                    new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
            OutputStream out = socket.getOutputStream();
            String line;
            while (running.get() && (line = reader.readLine()) != null) {
                if (line.trim().isEmpty()) {
                    continue;
                }
                if (line.getBytes(StandardCharsets.UTF_8).length > MAX_LINE_BYTES) {
                    writeLine(out, errorResponse(null, -32607, "request too large"));
                    continue;
                }
                String response = dispatch(line);
                writeLine(out, response);
            }
        } catch (IOException e) {
            Log.d(TAG, "client connection ended: " + e.getMessage());
        }
    }

    /** Parse one request line and produce one response line. */
    String dispatch(String requestJson) {
        String id = extractStringField(requestJson, "id");
        String method = extractStringField(requestJson, "method");
        if (method == null || method.isEmpty()) {
            return errorResponse(id, -32600, "invalid request: missing method");
        }
        String params = extractParams(requestJson);
        try {
            Object result = handler.handle(method, params == null ? "{}" : params);
            if (id == null || id.isEmpty()) {
                return ""; // notification: no response expected
            }
            String resultJson = result == null ? "null" : result.toString();
            return "{\"jsonrpc\":\"2.0\",\"id\":" + id + ",\"result\":" + resultJson + "}";
        } catch (Exception e) {
            Log.w(TAG, "method " + method + " failed: " + e.getMessage());
            return errorResponse(id, -32000, e.getMessage() == null ? "internal error" : e.getMessage());
        }
    }

    private static String errorResponse(String id, int code, String message) {
        String safeId = (id == null || id.isEmpty()) ? "null" : id;
        String safeMessage = message == null ? "internal error"
                : message.replace("\\", "\\\\").replace("\"", "\\\"")
                         .replace("\n", "\\n").replace("\r", "\\r");
        return "{\"jsonrpc\":\"2.0\",\"id\":" + safeId
                + ",\"error\":{\"code\":" + code + ",\"message\":\"" + safeMessage + "\"}}";
    }

    private static void writeLine(OutputStream out, String payload) {
        try {
            if (payload == null || payload.isEmpty()) {
                return;
            }
            out.write((payload + "\n").getBytes(StandardCharsets.UTF_8));
            out.flush();
        } catch (IOException e) {
            Log.d(TAG, "write failed: " + e.getMessage());
        }
    }

    /** Minimal string-field extraction without pulling in a JSON library. */
    private static String extractStringField(String json, String field) {
        if (json == null) {
            return null;
        }
        String needle = "\"" + field + "\"";
        int idx = json.indexOf(needle);
        if (idx < 0) {
            return null;
        }
        idx = json.indexOf(':', idx + needle.length());
        if (idx < 0) {
            return null;
        }
        int i = idx + 1;
        while (i < json.length() && Character.isWhitespace(json.charAt(i))) {
            i++;
        }
        if (i >= json.length()) {
            return null;
        }
        if (json.charAt(i) == '"') {
            StringBuilder sb = new StringBuilder();
            i++;
            while (i < json.length()) {
                char c = json.charAt(i);
                if (c == '\\' && i + 1 < json.length()) {
                    char next = json.charAt(i + 1);
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
        if (json.charAt(i) == 'n') {
            return null; // null literal
        }
        // numeric id (or literal): return raw token
        int start = i;
        while (i < json.length() && ",}".indexOf(json.charAt(i)) < 0) {
            i++;
        }
        return json.substring(start, i).trim();
    }

    private static String extractParams(String json) {
        if (json == null) {
            return null;
        }
        String needle = "\"params\"";
        int idx = json.indexOf(needle);
        if (idx < 0) {
            return "{}";
        }
        idx = json.indexOf(':', idx + needle.length());
        if (idx < 0) {
            return "{}";
        }
        int start = idx + 1;
        while (start < json.length() && Character.isWhitespace(json.charAt(start))) {
            start++;
        }
        if (start >= json.length()) {
            return "{}";
        }
        char open = json.charAt(start);
        char close;
        if (open == '{') {
            close = '}';
        } else if (open == '[') {
            close = ']';
        } else {
            return "{}";
        }
        int depth = 0;
        boolean inString = false;
        for (int i = start; i < json.length(); i++) {
            char c = json.charAt(i);
            if (inString) {
                if (c == '\\') {
                    i++;
                } else if (c == '"') {
                    inString = false;
                }
                continue;
            }
            if (c == '"') {
                inString = true;
            } else if (c == open) {
                depth++;
            } else if (c == close) {
                depth--;
                if (depth == 0) {
                    return json.substring(start, i + 1);
                }
            }
        }
        return "{}";
    }

    private static void closeQuietly(Socket socket) {
        try {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
        } catch (IOException ignored) {
        }
    }
}
