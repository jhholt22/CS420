package com.aeromind.network;

import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public class PythonBridgeClient {

    private final String host;
    private final int port;

    private Socket socket;
    private PrintWriter out;

    public PythonBridgeClient(String host, int port) {
        this.host = host;
        this.port = port;
    }

    public synchronized void connect() throws Exception {
        close();
        socket = new Socket(host, port);
        out = new PrintWriter(
                new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8),
                true
        );
    }

    public synchronized boolean isConnected() {
        return socket != null && socket.isConnected() && !socket.isClosed();
    }

    public synchronized void ensureConnected() {
        if (isConnected()) return;
        try {
            System.out.println("[UI] Reconnecting to Python...");
            connect();
            System.out.println("[UI] Reconnected to Python");
        } catch (Exception e) {
            System.out.println("[UI] Reconnect failed: " + e.getMessage());
        }
    }

    public void sendJsonLine(String json) {
        synchronized (this) {
            if (!isConnected() || out == null) {
                System.out.println("[UI] Not connected to Python");
                return;
            }
            out.println(json);
        }
    }

    public synchronized void close() {
        try {
            if (socket != null) socket.close();
        } catch (Exception ignored) {}
        socket = null;
        out = null;
    }
}