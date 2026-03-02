package com.aeromind.video;

import javafx.application.Platform;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;

import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

public class MjpegStreamReader {

    private final String url;
    private final ImageView target;

    private volatile boolean running = false;
    private Thread thread;

    // prevent FX queue spam
    private final AtomicBoolean updatePending = new AtomicBoolean(false);
    private final AtomicReference<Image> latestImage = new AtomicReference<>(null);

    // cap UI updates (fps)
    private final long minUiIntervalNs = 1_000_000_000L / 15; // 15 FPS max
    private volatile long lastUiUpdateNs = 0;

    public MjpegStreamReader(String url, ImageView target) {
        this.url = url;
        this.target = target;
    }

    public void start() {
        if (running) return;
        running = true;

        thread = new Thread(this::runLoop, "mjpeg-reader");
        thread.setDaemon(true);
        thread.start();
    }

    public void stop() {
        running = false;
        if (thread != null) {
            try { thread.join(800); } catch (InterruptedException ignored) {}
        }
    }

    private void runLoop() {
        HttpURLConnection conn = null;
        InputStream in = null;

        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(0); // streaming, do NOT timeout read
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
            System.out.println("[UI] MJPEG error: " + e.getMessage());
        } finally {
            try { if (in != null) in.close(); } catch (Exception ignored) {}
            if (conn != null) conn.disconnect();
        }
    }

    private void handleFrame(byte[] jpgBytes) {
        long now = System.nanoTime();
        if (now - lastUiUpdateNs < minUiIntervalNs) return; // drop frames
        lastUiUpdateNs = now;

        // decode OFF JavaFX thread
        Image img;
        try {
            img = new Image(new ByteArrayInputStream(jpgBytes), 0, 0, true, true);
        } catch (Exception ex) {
            return;
        }

        latestImage.set(img);

        // schedule only one FX update at a time
        if (updatePending.compareAndSet(false, true)) {
            Platform.runLater(() -> {
                try {
                    Image latest = latestImage.getAndSet(null);
                    if (latest != null) target.setImage(latest);
                } finally {
                    updatePending.set(false);
                }
            });
        }
    }
}