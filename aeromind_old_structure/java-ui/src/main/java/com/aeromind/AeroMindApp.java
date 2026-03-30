package com.aeromind;

import com.aeromind.network.PythonBridgeClient;
import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Scene;
import javafx.stage.Stage;

public class AeroMindApp extends Application {

    private PythonBridgeClient bridge;
    private MainWindow mainWindow;

    @Override
    public void start(Stage stage) {
        bridge = new PythonBridgeClient("127.0.0.1", 7070);

        StatusPanel statusPanel = new StatusPanel();
        bridge.setEventListener(new PythonBridgeClient.BridgeEventListener() {
            @Override
            public void onConnectionChanged(boolean connected) {
                statusPanel.setConnectionState(connected ? "Connected" : "Disconnected");
            }

            @Override
            public void onError(String errorMessage) {
                statusPanel.appendError(errorMessage);
            }
        });

        bridge.ensureConnected();

        DroneCommandService commandService = new DroneCommandService(
                bridge,
                statusPanel::setLastCommand,
                statusPanel::appendError
        );

        mainWindow = new MainWindow(bridge, commandService, statusPanel);

        Scene scene = new Scene(mainWindow.getRoot(), 1000, 760);
        mainWindow.installKeyboardControls(scene);

        stage.setTitle("AeroMind Control Panel");
        stage.setScene(scene);
        stage.show();

        stage.setOnCloseRequest(event -> {
            mainWindow.shutdown();
            bridge.close();
            Platform.exit();
            System.exit(0);
        });
    }

    public static void main(String[] args) {
        launch(args);
    }
}