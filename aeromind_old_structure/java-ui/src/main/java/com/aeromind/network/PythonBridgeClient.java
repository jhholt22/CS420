package com.aeromind.network;

import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

public class PythonBridgeClient {

    public interface BridgeEventListener {
        void onConnectionChanged(boolean connected);
        void onError(String errorMessage);
    }

    private final String host;
    private final int port;

    private Socket socket;
    private PrintWriter out;
    private BridgeEventListener eventListener;

    public PythonBridgeClient(String host, int port) {
        this.host = host;
        this.port = port;
    }

    public synchronized void setEventListener(BridgeEventListener listener) {
        this.eventListener = listener;
    }

    public synchronized void connect() throws Exception {
        close();
        socket = new Socket();
        socket.connect(new InetSocketAddress(host, port), 1500);
        out = new PrintWriter(
                new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8),
                true
        );
        notifyConnection(true);
    }

    public synchronized boolean isConnected() {
        return socket != null && socket.isConnected() && !socket.isClosed();
    }

    public synchronized void ensureConnected() {
        if (isConnected()) {
            notifyConnection(true);
            return;
        }

        try {
            connect();
        } catch (Exception e) {
            notifyConnection(false);
            notifyError("Reconnect failed: " + e.getMessage());
        }
    }

    public synchronized boolean sendJsonLine(String json) {
        if (!isConnected() || out == null) {
            ensureConnected();
            if (!isConnected()) {
                notifyError("Not connected to Python bridge");
                return false;
            }
        }

        try {
            out.println(json);
            if (out.checkError()) {
                notifyError("Bridge write failed");
                notifyConnection(false);
                return false;
            }
            return true;
        } catch (Exception e) {
            notifyError("Bridge send error: " + e.getMessage());
            notifyConnection(false);
            return false;
        }
    }

    public synchronized void close() {
        try {
            if (socket != null) {
                socket.close();
            }
        } catch (Exception ignored) {
        }

        socket = null;
        out = null;
        notifyConnection(false);
    }

    private void notifyConnection(boolean connected) {
        if (eventListener != null) {
            eventListener.onConnectionChanged(connected);
        }
    }

    private void notifyError(String message) {
        if (eventListener != null) {
            eventListener.onError(message);
        }
    }
}