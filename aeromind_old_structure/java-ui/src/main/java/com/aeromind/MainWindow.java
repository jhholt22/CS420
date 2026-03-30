package com.aeromind;

import com.aeromind.network.PythonBridgeClient;
import javafx.animation.KeyFrame;
import javafx.animation.Timeline;
import javafx.geometry.Insets;
import javafx.scene.Scene;
import javafx.scene.input.KeyCode;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.VBox;
import javafx.util.Duration;

public class MainWindow {

    private final BorderPane root;
    private final DroneCommandService commandService;
    private final VideoPanel videoPanel;
    private final Timeline connectionPoller;

    public MainWindow(PythonBridgeClient bridge, DroneCommandService commandService, StatusPanel statusPanel) {
        this.root = new BorderPane();
        this.commandService = commandService;
        this.videoPanel = new VideoPanel("http://127.0.0.1:8080/video");

        FlightControls flightControls = new FlightControls(commandService, bridge::ensureConnected);
        MovementControls movementControls = new MovementControls(commandService);
        ControlPanel controlPanel = new ControlPanel(flightControls, movementControls);

        VBox bottom = new VBox(12, controlPanel.getRoot(), statusPanel.getRoot());
        bottom.setPadding(new Insets(12));

        root.setPadding(new Insets(10));
        root.setCenter(videoPanel.getRoot());
        root.setBottom(bottom);

        connectionPoller = new Timeline(new KeyFrame(Duration.seconds(1), evt ->
                statusPanel.setConnectionState(bridge.isConnected() ? "Connected" : "Disconnected")
        ));
        connectionPoller.setCycleCount(Timeline.INDEFINITE);
        connectionPoller.play();
    }

    public BorderPane getRoot() {
        return root;
    }

    public void installKeyboardControls(Scene scene) {
        scene.setOnKeyPressed(event -> {
            KeyCode code = event.getCode();
            switch (code) {
                case W -> commandService.sendForward(30);
                case S -> commandService.sendBack(30);
                case A -> commandService.sendLeft(30);
                case D -> commandService.sendRight(30);
                case UP -> commandService.sendUp(30);
                case DOWN -> commandService.sendDown(30);
                case LEFT -> commandService.sendRotateCCW(45);
                case RIGHT -> commandService.sendRotateCW(45);
                case SPACE -> commandService.sendTakeoff();
                case L -> commandService.sendLand();
                case E -> commandService.sendEmergency();
                default -> {
                }
            }
        });
    }

    public void shutdown() {
        connectionPoller.stop();
        videoPanel.stop();
    }
}
