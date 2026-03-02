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

    public void connect() throws Exception {
        socket = new Socket(host, port);
        out = new PrintWriter(
                new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8),
                true
        );
    }

    public void sendJsonLine(String json) {
        if (out == null) {
            System.out.println("[UI] Not connected to Python");
            return;
        }
        out.println(json);
    }

    public void close() {
        try {
            if (socket != null) socket.close();
        } catch (Exception ignored) {}
        socket = null;
        out = null;
    }
}