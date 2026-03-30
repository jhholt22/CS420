package com.aeromind;

import com.aeromind.network.PythonBridgeClient;

import java.util.function.Consumer;

public class DroneCommandService {

    private static final long COMMAND_COOLDOWN_MS = 300;

    private final PythonBridgeClient bridge;
    private final Consumer<String> lastCommandSink;
    private final Consumer<String> errorSink;

    private long lastSentAt;

    public DroneCommandService(PythonBridgeClient bridge, Consumer<String> lastCommandSink, Consumer<String> errorSink) {
        this.bridge = bridge;
        this.lastCommandSink = lastCommandSink;
        this.errorSink = errorSink;
        this.lastSentAt = 0;
    }

    public void sendTakeoff() {
        send("takeoff");
    }

    public void sendLand() {
        send("land");
    }

    public void sendEmergency() {
        send("emergency");
    }

    public void sendRecover() {
        send("recover");
    }

    public void sendForward(int cm) {
        send("forward " + clamp(cm, 20, 500));
    }

    public void sendBack(int cm) {
        send("back " + clamp(cm, 20, 500));
    }

    public void sendLeft(int cm) {
        send("left " + clamp(cm, 20, 500));
    }

    public void sendRight(int cm) {
        send("right " + clamp(cm, 20, 500));
    }

    public void sendUp(int cm) {
        send("up " + clamp(cm, 20, 500));
    }

    public void sendDown(int cm) {
        send("down " + clamp(cm, 20, 500));
    }

    public void sendRotateCW(int deg) {
        send("cw " + clamp(deg, 1, 360));
    }

    public void sendRotateCCW(int deg) {
        send("ccw " + clamp(deg, 1, 360));
    }

    public void sendSpeed(int value) {
        send("speed " + clamp(value, 10, 100));
    }

    private synchronized void send(String command) {
        long now = System.currentTimeMillis();
        if (now - lastSentAt < COMMAND_COOLDOWN_MS) {
            if (errorSink != null) {
                errorSink.accept("Command throttled: " + command);
            }
            return;
        }
        lastSentAt = now;

        bridge.ensureConnected();
        String json = "{\"type\":\"CMD\",\"cmd\":\"" + command + "\"}";
        boolean ok = bridge.sendJsonLine(json);

        if (ok) {
            if (lastCommandSink != null) {
                lastCommandSink.accept(command);
            }
        } else if (errorSink != null) {
            errorSink.accept("Failed to send command: " + command);
        }
    }

    private int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }
}