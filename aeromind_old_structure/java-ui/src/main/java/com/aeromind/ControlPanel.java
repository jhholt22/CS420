package com.aeromind;

import javafx.geometry.Pos;
import javafx.scene.control.Label;
import javafx.scene.layout.VBox;

public class ControlPanel {

    private final VBox root;

    public ControlPanel(FlightControls flightControls, MovementControls movementControls) {
        Label movementTitle = new Label("MOVEMENT");
        movementTitle.setStyle("-fx-font-size: 14px; -fx-font-weight: bold;");

        root = new VBox(8, flightControls.getRoot(), movementTitle, movementControls.getRoot());
        root.setAlignment(Pos.CENTER);
    }

    public VBox getRoot() {
        return root;
    }
}