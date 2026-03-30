package com.aeromind.video;

import javafx.application.Platform;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;

import java.io.BufferedInputStream;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

public class MjpegStreamReader {

    private final String url;
    private final ImageView target;
    private final Runnable frameCallback;
    private final Consumer<String> errorCallback;

    private volatile boolean running = false;
    private Thread thread;

    private final AtomicBoolean updatePending = new AtomicBoolean(false);
    private final AtomicReference<Image> latestImage = new AtomicReference<>(null);

    private final long minUiIntervalNs = 1_000_000_000L / 15;
    private volatile long lastUiUpdateNs = 0;

    public MjpegStreamReader(String url, ImageView target) {
        this(url, target, null, null);
    }

    public MjpegStreamReader(String url, ImageView target, Runnable frameCallback, Consumer<String> errorCallback) {
        this.url = url;
        this.target = target;
        this.frameCallback = frameCallback;
        this.errorCallback = errorCallback;
    }

    public void start() {
        if (running) {
            return;
        }
        running = true;

        thread = new Thread(this::runLoop, "mjpeg-reader");
        thread.setDaemon(true);
        thread.start();
    }

    public void stop() {
        running = false;
        if (thread != null) {
            try {
                thread.join(800);
            } catch (InterruptedException ignored) {
            }
        }
    }

    private void runLoop() {
        HttpURLConnection conn = null;
        InputStream in = null;

        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(0);
            conn.connect();

            in = new BufferedInputStream(conn.getInputStream());

            byte[] buffer = new byte[1024 * 128];
            int len;
            ByteArrayOutputStream frameBuf = new ByteArrayOutputStream();

            boolean inJpeg = false;
            byte prev = 0;

            while (running && (len = in.read(buffer)) != -1) {
                for (int i = 0; i < len; i++) {
                    byte b = buffer[i];

                    if (!inJpeg) {
                        if (prev == (byte) 0xFF && b == (byte) 0xD8) {
                            inJpeg = true;
                            frameBuf.reset();
                            frameBuf.write(0xFF);
                            frameBuf.write(0xD8);
                        }
                    } else {
                        frameBuf.write(b & 0xFF);

                        if (prev == (byte) 0xFF && b == (byte) 0xD9) {
                            byte[] jpg = frameBuf.toByteArray();
                            handleFrame(jpg);
                            inJpeg = false;
                        }
                    }

                    prev = b;
                }
            }

        } catch (Exception e) {
            reportError("MJPEG error: " + e.getMessage());
        } finally {
            try {
                if (in != null) {
                    in.close();
                }
            } catch (Exception ignored) {
            }
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private void handleFrame(byte[] jpgBytes) {
        long now = System.nanoTime();
        if (now - lastUiUpdateNs < minUiIntervalNs) {
            return;
        }
        lastUiUpdateNs = now;

        Image img;
        try {
            img = new Image(new ByteArrayInputStream(jpgBytes), 0, 0, true, true);
        } catch (Exception ex) {
            return;
        }

        latestImage.set(img);

        if (updatePending.compareAndSet(false, true)) {
            Platform.runLater(() -> {
                try {
                    Image latest = latestImage.getAndSet(null);
                    if (latest != null) {
                        target.setImage(latest);
                        if (frameCallback != null) {
                            frameCallback.run();
                        }
                    }
                } finally {
                    updatePending.set(false);
                }
            });
        }
    }

    private void reportError(String message) {
        if (errorCallback != null) {
            errorCallback.accept(message);
        }
    }
}