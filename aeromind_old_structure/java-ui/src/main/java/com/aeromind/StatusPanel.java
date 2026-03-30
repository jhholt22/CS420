package com.aeromind;

import javafx.geometry.Insets;
import javafx.scene.control.Label;
import javafx.scene.control.TextArea;
import javafx.scene.layout.VBox;

public class StatusPanel {

    private final VBox root;
    private final Label lastCommandValue;
    private final Label connectionValue;
    private final TextArea errors;

    public StatusPanel() {
        Label title = new Label("Status");
        title.setStyle("-fx-font-size: 13px; -fx-font-weight: bold;");

        lastCommandValue = new Label("-");
        connectionValue = new Label("Disconnected");

        Label lastCommandLabel = new Label("Last command: ");
        Label connectionLabel = new Label("Connection: ");
        Label errorsLabel = new Label("Bridge errors:");

        errors = new TextArea();
        errors.setEditable(false);
        errors.setWrapText(true);
        errors.setPrefRowCount(4);

        VBox cmdRow = new VBox(2, lastCommandLabel, lastCommandValue);
        VBox connRow = new VBox(2, connectionLabel, connectionValue);

        root = new VBox(6, title, cmdRow, connRow, errorsLabel, errors);
        root.setPadding(new Insets(8));
        root.setStyle("-fx-border-color: #A0A0A0; -fx-border-width: 1; -fx-background-color: #F7F7F7;");
    }

    public VBox getRoot() {
        return root;
    }

    public void setLastCommand(String command) {
        lastCommandValue.setText(command == null ? "-" : command);
    }

    public void setConnectionState(String state) {
        connectionValue.setText(state == null ? "Unknown" : state);
    }

    public void appendError(String errorMessage) {
        if (errorMessage == null || errorMessage.isBlank()) {
            return;
        }
        errors.appendText(errorMessage + "\n");
    }
}