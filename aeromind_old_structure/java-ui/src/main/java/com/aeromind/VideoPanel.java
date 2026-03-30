package com.aeromind;

import com.aeromind.video.MjpegStreamReader;
import javafx.application.Platform;
import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.image.ImageView;
import javafx.scene.layout.StackPane;

public class VideoPanel {

    private final StackPane root;
    private final MjpegStreamReader reader;
    private final Label noVideo;
    private volatile long lastFrameMillis;

    public VideoPanel(String streamUrl) {
        ImageView videoView = new ImageView();
        videoView.setFitWidth(900);
        videoView.setFitHeight(480);
        videoView.setPreserveRatio(true);

        Label overlay = new Label("AeroMind Drone Feed");
        overlay.setStyle("-fx-background-color: rgba(0,0,0,0.55); -fx-text-fill: white; -fx-padding: 6 10 6 10;");
        StackPane.setAlignment(overlay, Pos.TOP_LEFT);

        noVideo = new Label("NO VIDEO");
        noVideo.setStyle("-fx-text-fill: white; -fx-font-size: 24px; -fx-font-weight: bold;");
        StackPane.setAlignment(noVideo, Pos.CENTER);

        root = new StackPane(videoView, noVideo, overlay);
        root.setStyle("-fx-background-color: black; -fx-border-color: #4A4A4A; -fx-border-width: 2;");
        root.setMinHeight(500);

        lastFrameMillis = System.currentTimeMillis();
        reader = new MjpegStreamReader(
                streamUrl,
                videoView,
                () -> {
                    lastFrameMillis = System.currentTimeMillis();
                    Platform.runLater(() -> noVideo.setVisible(false));
                },
                error -> Platform.runLater(() -> noVideo.setVisible(true))
        );
        reader.start();

        Thread noVideoWatcher = new Thread(() -> {
            while (!Thread.currentThread().isInterrupted()) {
                if (System.currentTimeMillis() - lastFrameMillis > 2000) {
                    Platform.runLater(() -> noVideo.setVisible(true));
                }
                try {
                    Thread.sleep(500);
                } catch (InterruptedException ignored) {
                    Thread.currentThread().interrupt();
                }
            }
        }, "video-watchdog");
        noVideoWatcher.setDaemon(true);
        noVideoWatcher.start();
    }

    public StackPane getRoot() {
        return root;
    }

    public void stop() {
        reader.stop();
    }
}