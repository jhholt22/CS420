package com.aeromind;

import com.aeromind.network.PythonBridgeClient;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;

public class AeroMindApp extends Application {

    private PythonBridgeClient bridge;

    @Override
    public void start(Stage stage) {

        bridge = new PythonBridgeClient("127.0.0.1", 7070);

        try {
            bridge.connect();
            System.out.println("[UI] Connected to Python");
        } catch (Exception e) {
            System.out.println("[UI] Could not connect to Python: " + e.getMessage());
        }

        // ---------------- Buttons ----------------

        Button emergencyBtn = new Button("EMERGENCY");
        emergencyBtn.setStyle(
                "-fx-background-color: red;" +
                        "-fx-text-fill: white;" +
                        "-fx-font-size: 18px;" +
                        "-fx-padding: 10 20 10 20;"
        );

        emergencyBtn.setOnAction(e -> {
            System.out.println("[UI] Emergency clicked");
            sendCommand("emergency");
        });

        Button takeoffBtn = new Button("TAKEOFF");
        takeoffBtn.setOnAction(e -> {
            System.out.println("[UI] Takeoff clicked");
            sendCommand("takeoff");
        });

        Button landBtn = new Button("LAND");
        landBtn.setOnAction(e -> {
            System.out.println("[UI] Land clicked");
            sendCommand("land");
        });

        HBox controls = new HBox(20, takeoffBtn, landBtn);
        controls.setStyle("-fx-alignment: center;");

        VBox root = new VBox(40, emergencyBtn, controls);
        root.setStyle(
                "-fx-padding: 40;" +
                        "-fx-alignment: center;"
        );

        stage.setTitle("AeroMind Control Panel");
        stage.setScene(new Scene(root, 700, 450));
        stage.show();

        stage.setOnCloseRequest(event -> {
            System.out.println("[UI] Closing UI");
            bridge.close();
            Platform.exit();
            System.exit(0);
        });
    }

    private void sendCommand(String cmd) {
        if (bridge == null) return;

        String json = String.format(
                "{\"type\":\"CMD\",\"cmd\":\"%s\"}",
                cmd
        );

        bridge.sendJsonLine(json);
    }

    public static void main(String[] args) {
        launch(args);
    }
}