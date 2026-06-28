package com.agricol.desktop;

import com.agricol.desktop.controller.MainController;
import javafx.application.Application;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.scene.text.Font;
import javafx.stage.Stage;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class DesktopApp extends Application {

    private final HttpClient client = HttpClient.newHttpClient();

    @Override
    public void start(Stage stage) {
        showLogin(stage);
    }

    private void showLogin(Stage stage) {
        VBox root = new VBox(15);
        root.setAlignment(Pos.CENTER);
        root.setPadding(new Insets(40));
        root.setStyle("-fx-background: linear-gradient(to bottom right, #1b5e20, #388e3c);");

        Label titre = new Label("AgriCol");
        titre.setFont(Font.font("System", 36));
        titre.setTextFill(Color.WHITE);
        Label sousTitre = new Label("Système d'Irrigation Intelligent");
        sousTitre.setFont(Font.font("System", 16));
        sousTitre.setTextFill(Color.web("#c8e6c9"));

        VBox card = new VBox(12);
        card.setPadding(new Insets(30));
        card.setMaxWidth(380);
        card.setStyle("-fx-background-color: white; -fx-border-radius: 12; -fx-background-radius: 12; -fx-effect: dropshadow(three-pass-box, rgba(0,0,0,0.2), 10, 0, 0, 4);");
        card.setAlignment(Pos.CENTER);

        Label cardTitre = new Label("Connexion");
        cardTitre.setFont(Font.font("System", 20));

        TextField emailF = new TextField();
        emailF.setPromptText("Email");
        emailF.setMaxWidth(320);
        PasswordField mdpF = new PasswordField();
        mdpF.setPromptText("Mot de passe");
        mdpF.setMaxWidth(320);

        Label erreur = new Label();
        erreur.setTextFill(Color.RED);
        erreur.setWrapText(true);
        erreur.setMaxWidth(320);

        Button loginBtn = new Button("Se connecter");
        loginBtn.setMaxWidth(320);
        loginBtn.setStyle("-fx-background-color: #2e7d32; -fx-text-fill: white; -fx-font-weight: bold; -fx-padding: 10; -fx-background-radius: 6;");

        loginBtn.setOnAction(e -> {
            try {
                String json = String.format("{\"email\":\"%s\",\"motDePasse\":\"%s\"}", emailF.getText(), mdpF.getText());
                HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create("http://localhost:8080/api/auth/login"))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
                HttpResponse<String> resp = client.send(req, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() == 200) {
                    String body = resp.body();
                    String token = body.replaceAll(".*\"token\":\"([^\"]+)\".*", "$1");
                    showMain(stage, token);
                } else {
                    erreur.setText("Erreur d'authentification");
                }
            } catch (Exception ex) {
                erreur.setText("Connexion au serveur impossible:\n" + ex.getMessage());
            }
        });

        card.getChildren().addAll(cardTitre, emailF, mdpF, loginBtn, erreur);
        root.getChildren().addAll(titre, sousTitre, card);

        Scene scene = new Scene(root, 1400, 900);
        stage.setTitle("AgriCol - Connexion");
        stage.setScene(scene);
        stage.show();
    }

    private void showMain(Stage stage, String token) {
        MainController mc = new MainController(stage, token);

        TabPane tabs = new TabPane();
        tabs.getTabs().addAll(
            tab("Dashboard", mc.getDashboardView()),
            tab("Espaces", mc.getEspaceGestionView()),
            tab("Zones", mc.getZoneGestionView()),
            tab("Utilisateurs", mc.getUserGestionView()),
            tab("Rapports", mc.getRapportView())
        );
        tabs.getTabs().forEach(t -> t.setClosable(false));

        Scene scene = new Scene(tabs, 1400, 900);
        scene.getStylesheets().add(getClass().getResource("/styles.css").toExternalForm());
        stage.setTitle("AgriCol - Gestion Irrigation Intelligente");
        stage.setScene(scene);
    }

    private Tab tab(String nom, javafx.scene.Node content) {
        Tab t = new Tab(nom);
        t.setContent(content);
        return t;
    }

    public static void main(String[] args) {
        launch();
    }
}
