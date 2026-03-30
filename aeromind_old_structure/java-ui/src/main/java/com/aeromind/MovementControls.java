package com.aeromind;

import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.control.Button;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.VBox;

public class MovementControls {

    private final VBox root;

    public MovementControls(DroneCommandService commandService) {
        root = new VBox(8);
        root.setAlignment(Pos.CENTER);

        GridPane grid = new GridPane();
        grid.setHgap(8);
        grid.setVgap(8);
        grid.setAlignment(Pos.CENTER);
        grid.setPadding(new Insets(8, 0, 8, 0));

        Button forward = button("FORWARD", () -> commandService.sendForward(30));
        Button back = button("BACK", () -> commandService.sendBack(30));
        Button left = button("LEFT", () -> commandService.sendLeft(30));
        Button right = button("RIGHT", () -> commandService.sendRight(30));
        Button up = button("UP", () -> commandService.sendUp(30));
        Button down = button("DOWN", () -> commandService.sendDown(30));
        Button rotateLeft = button("ROTATE L", () -> commandService.sendRotateCCW(45));
        Button rotateRight = button("ROTATE R", () -> commandService.sendRotateCW(45));

        grid.add(forward, 1, 0);
        grid.add(left, 0, 1);
        grid.add(right, 2, 1);
        grid.add(back, 1, 2);

        grid.add(up, 0, 3);
        grid.add(down, 1, 3);

        grid.add(rotateLeft, 0, 4);
        grid.add(rotateRight, 1, 4);

        root.getChildren().add(grid);
    }

    private Button button(String text, Runnable action) {
        Button b = new Button(text);
        b.setMinWidth(120);
        b.setMinHeight(38);
        b.setOnAction(e -> action.run());
        return b;
    }

    public VBox getRoot() {
        return root;
    }
}