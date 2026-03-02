package com.aeromind;

import com.aeromind.network.PythonBridgeClient;
import com.aeromind.video.MjpegStreamReader;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.image.ImageView;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;

public class AeroMindApp extends Application {

    private PythonBridgeClient bridge;
    private MjpegStreamReader mjpeg;

    @Override
    public void start(Stage stage) {

        // ---------- Connect to Python (TCP control/telemetry) ----------
        bridge = new PythonBridgeClient("127.0.0.1", 7070);
        try {
            bridge.connect();
            System.out.println("[UI] Connected to Python");
        } catch (Exception e) {
            System.out.println("[UI] Could not connect to Python: " + e.getMessage());
        }

        // ---------- Video (MJPEG over HTTP) ----------
        ImageView videoView = new ImageView();
        videoView.setFitWidth(640);
        videoView.setFitHeight(480);
        videoView.setPreserveRatio(true);

        mjpeg = new MjpegStreamReader("http://127.0.0.1:8080/video", videoView);
        mjpeg.start();

        // ---------- Buttons ----------
        Button emergencyBtn = new Button("EMERGENCY");
        emergencyBtn.setStyle(
                "-fx-background-color: red;" +
                        "-fx-text-fill: white;" +
                        "-fx-font-size: 18px;" +
                        "-fx-padding: 10 20 10 20;"
        );
        emergencyBtn.setOnAction(e -> {
            System.out.println("[UI] Emergency clicked");
            bridge.ensureConnected();
            sendCommand("emergency");
        });

        Button recoverBtn = new Button("RECOVER");
        recoverBtn.setStyle(
                "-fx-background-color: blue;" +
                        "-fx-text-fill: white;" +
                        "-fx-font-size: 13px;" +
                        "-fx-padding: 10 20 10 20;"
        );
        recoverBtn.setOnAction(e -> {
            System.out.println("[UI] Recover clicked");
            bridge.ensureConnected();
            sendCommand("recover");
        });

        Button takeoffBtn = new Button("TAKEOFF");
        takeoffBtn.setOnAction(e -> {
            System.out.println("[UI] Takeoff clicked");
            bridge.ensureConnected();
            sendCommand("takeoff");
        });

        Button landBtn = new Button("LAND");
        landBtn.setOnAction(e -> {
            System.out.println("[UI] Land clicked");
            bridge.ensureConnected();
            sendCommand("land");
        });

        HBox topControls = new HBox(20, emergencyBtn, recoverBtn);
        topControls.setStyle("-fx-alignment: center;");

        HBox flightControls = new HBox(20, takeoffBtn, landBtn);
        flightControls.setStyle("-fx-alignment: center;");

        VBox root = new VBox(20, videoView, topControls, flightControls);
        root.setStyle("-fx-padding: 20; -fx-alignment: center;");

        stage.setTitle("AeroMind Control Panel");
        stage.setScene(new Scene(root, 900, 700));
        stage.show();

        // ---------- Clean shutdown ----------
        stage.setOnCloseRequest(event -> {
            System.out.println("[UI] Closing UI");
            if (mjpeg != null) mjpeg.stop();
            if (bridge != null) bridge.close();
            Platform.exit();
            System.exit(0);
        });
    }

    private void sendCommand(String cmd) {
        if (bridge == null) return;
        String json = String.format("{\"type\":\"CMD\",\"cmd\":\"%s\"}", cmd);
        bridge.sendJsonLine(json);
    }

    public static void main(String[] args) {
        launch(args);
    }
}