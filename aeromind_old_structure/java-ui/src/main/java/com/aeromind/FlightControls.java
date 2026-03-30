package com.aeromind;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.Slider;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;

public class FlightControls {

    private final VBox root;

    public FlightControls(DroneCommandService commandService, Runnable reconnectAction) {
        root = new VBox(10);
        root.setAlignment(Pos.CENTER);
        root.setPadding(new Insets(2, 0, 4, 0));

        HBox flightButtons = new HBox(10,
                button("TAKEOFF", commandService::sendTakeoff),
                button("LAND", commandService::sendLand),
                button("EMERGENCY", commandService::sendEmergency),
                button("RECOVER", commandService::sendRecover),
                button("RECONNECT", reconnectAction)
        );
        flightButtons.setAlignment(Pos.CENTER);

        Label speedLabel = new Label("Speed: 50");
        Slider speedSlider = new Slider(10, 100, 50);
        speedSlider.setBlockIncrement(1);
        speedSlider.setMajorTickUnit(10);
        speedSlider.setMinorTickCount(0);
        speedSlider.setSnapToTicks(true);
        speedSlider.setShowTickLabels(true);
        speedSlider.setShowTickMarks(true);
        speedSlider.setPrefWidth(320);

        speedSlider.valueProperty().addListener((obs, oldV, newV) -> {
            int speed = newV.intValue();
            speedLabel.setText("Speed: " + speed);
            commandService.sendSpeed(speed);
        });

        HBox speedRow = new HBox(10, speedLabel, speedSlider);
        speedRow.setAlignment(Pos.CENTER);

        root.getChildren().addAll(flightButtons, speedRow);
    }

    private Button button(String text, Runnable action) {
        Button b = new Button(text);
        b.setMinHeight(38);
        b.setMinWidth(110);
        b.setOnAction(e -> action.run());
        return b;
    }

    public VBox getRoot() {
        return root;
    }
}