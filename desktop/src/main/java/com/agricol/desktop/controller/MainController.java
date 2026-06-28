package com.agricol.desktop.controller;

import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.chart.*;
import javafx.scene.control.*;
import javafx.scene.control.cell.PropertyValueFactory;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.scene.text.Font;
import javafx.stage.FileChooser;
import javafx.stage.Stage;

import java.io.File;
import java.io.FileWriter;
import java.nio.file.Files;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class MainController {

    private final HttpClient client = HttpClient.newHttpClient();
    private final String api = "http://localhost:8080/api";
    private final Stage stage;
    private final String token;

    public MainController(Stage stage, String token) {
        this.stage = stage;
        this.token = token;
    }

    private HttpRequest.Builder auth() {
        return HttpRequest.newBuilder()
            .header("Authorization", "Bearer " + token)
            .header("Content-Type", "application/json");
    }

    // ========== DASHBOARD ==========
    public BorderPane getDashboardView() {
        BorderPane root = new BorderPane();

        HBox header = new HBox(10);
        header.setPadding(new Insets(20));
        header.setStyle("-fx-background-color: linear-gradient(to right, #1b5e20, #388e3c);");
        Label titre = new Label("AgriCol - Système d'Irrigation Intelligent");
        titre.setFont(Font.font("System", 22));
        titre.setTextFill(Color.WHITE);

        Button refreshBtn = new Button("⟳ Rafraîchir");
        refreshBtn.setStyle("-fx-background-color: rgba(255,255,255,0.2); -fx-text-fill: white;");
        header.getChildren().addAll(titre, new Region(), refreshBtn);
        HBox.setHgrow(header.getChildren().get(1), Priority.ALWAYS);

        GridPane statsGrid = new GridPane();
        statsGrid.setPadding(new Insets(20));
        statsGrid.setHgap(20);
        statsGrid.setVgap(20);

        // Carte stats
        VBox stats = new VBox(10);
        stats.setPadding(new Insets(20));
        stats.setStyle(panneauStyle);
        Label statsTitle = new Label("Statistiques");
        statsTitle.setFont(Font.font("System", 16));
        Label statsContent = new Label("Appuyez sur Rafraîchir");
        stats.getChildren().addAll(statsTitle, statsContent);
        statsGrid.add(stats, 0, 0);

        // Graphique
        VBox chartBox = new VBox(10);
        chartBox.setPadding(new Insets(20));
        chartBox.setStyle(panneauStyle);
        CategoryAxis xAxis = new CategoryAxis();
        NumberAxis yAxis = new NumberAxis(0, 100, 10);
        LineChart<String, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setTitle("Évolution Humidité (Dernières 20 mesures)");
        chart.setPrefSize(600, 300);
        Label chartEmpty = new Label("Aucune donnée");
        chartBox.getChildren().addAll(new Label("Graphique d'évolution"), chartEmpty, chart);
        statsGrid.add(chartBox, 1, 0, 2, 1);

        // Alertes
        VBox alerts = new VBox(10);
        alerts.setPadding(new Insets(20));
        alerts.setStyle(panneauStyle);
        Label alertsTitle = new Label("Alertes");
        alertsTitle.setFont(Font.font("System", 16));
        VBox alertsList = new VBox(4);
        alertsList.getChildren().add(new Label("Appuyez sur Rafraîchir"));
        alerts.getChildren().addAll(alertsTitle, alertsList);
        statsGrid.add(alerts, 3, 0);

        // Refresh action with real data
        refreshBtn.setOnAction(e -> {
            try {
                String zonesJson = get(api + "/zones");

                if (zonesJson.equals("[]")) {
                    statsContent.setText("Aucune zone configurée.");
                    alertsList.getChildren().setAll(new Label("Aucune zone"));
                    chartEmpty.setVisible(true);
                    chart.setVisible(false);
                    return;
                }

                // Parse zones
                String[] zones = zonesJson.substring(1, zonesJson.length() - 1).split("\\},\\{");
                long totalZones = zones.length;
                long zonesActives = 0;
                long zonesAlarme = 0;
                double humiditeMoyenne = 0;
                StringBuilder alertText = new StringBuilder();
                VBox alertBox = new VBox(4);
                chart.getData().clear();
                chartEmpty.setVisible(false);
                chart.setVisible(true);
                Color[] couleurs = {Color.RED, Color.BLUE, Color.GREEN, Color.ORANGE, Color.PURPLE, Color.CYAN};

                for (int i = 0; i < zones.length; i++) {
                    String z = zones[i].replaceAll("[{}]", "");
                    String[] fields = z.split(",");
                    long id = 0; String nom = ""; double seuil = 0; double hum = -1; boolean active = false;
                    for (String f : fields) {
                        String[] kv = f.split(":", 2);
                        if (kv.length == 2) {
                            String k = kv[0].trim().replaceAll("\"", "");
                            String v = kv[1].trim().replaceAll("\"", "");
                            switch (k) {
                                case "id" -> id = Long.parseLong(v);
                                case "nom" -> nom = v;
                                case "seuilHumidite" -> seuil = v.equals("null") ? 0 : Double.parseDouble(v);
                                case "derniereHumidite" -> hum = v.equals("null") ? -1 : Double.parseDouble(v);
                                case "active" -> active = v.equals("true") || v.equals("null");
                            }
                        }
                    }

                    if (active) zonesActives++;
                    if (hum >= 0) {
                        humiditeMoyenne += hum;
                        if (hum < seuil) {
                            zonesAlarme++;
                            Label al = new Label("⚠ " + nom + " : " + String.format("%.1f", hum) + "% (seuil " + String.format("%.0f", seuil) + "%)");
                            al.setTextFill(Color.RED);
                            alertBox.getChildren().add(al);
                        }
                    }

                    // Charger mesures pour cette zone
                    try {
                        String mesuresJson = get(api + "/mesures/" + id);
                        if (mesuresJson.length() > 2) {
                            XYChart.Series<String, Number> series = new XYChart.Series<>();
                            series.setName(nom);
                            String[] mesures = mesuresJson.substring(1, mesuresJson.length() - 1).split("\\},\\{");
                            for (int j = mesures.length - 1; j >= 0; j--) {
                                String m = mesures[j].replaceAll("[{}]", "");
                                String[] mf = m.split(",");
                                double h = 0; String ts = "";
                                for (String f : mf) {
                                    String[] kv = f.split(":", 2);
                                    if (kv.length == 2) {
                                        String k = kv[0].trim().replaceAll("\"", "");
                                        String v = kv[1].trim().replaceAll("\"", "");
                                        if (k.equals("humidite")) h = Double.parseDouble(v);
                                        if (k.equals("timestamp")) ts = v.length() > 16 ? v.substring(11, 16) : v;
                                    }
                                }
                                series.getData().add(new XYChart.Data<>(ts, h));
                            }
                            chart.getData().add(series);
                            int ci = (chart.getData().size() - 1) % couleurs.length;
                            series.getNode().setStyle("-fx-stroke: " + toHex(couleurs[ci]) + ";");
                        }
                    } catch (Exception ignored) { }
                }

                if (zones.length > 0) humiditeMoyenne /= zones.length;
                String resume = "Zones: " + totalZones + " (" + zonesActives + " actives)\n"
                    + "Humidité moyenne: " + String.format("%.1f", humiditeMoyenne) + "%\n"
                    + "Alertes: " + zonesAlarme;
                statsContent.setText(resume);

                if (alertBox.getChildren().isEmpty()) {
                    alertBox.getChildren().add(new Label("✅ Aucune alerte - toutes les zones sont OK"));
                }
                alertsList.getChildren().setAll(alertBox.getChildren());

            } catch (Exception ex) {
                statsContent.setText("Erreur: " + ex.getMessage());
            }
        });

        root.setTop(header);
        root.setCenter(statsGrid);
        return root;
    }

    private static final String panneauStyle = "-fx-background-color: white; -fx-border-radius: 8; -fx-effect: dropshadow(three-pass-box, rgba(0,0,0,0.1), 5, 0, 0, 2);";

    private String get(String url) throws Exception {
        HttpRequest req = auth().uri(URI.create(url)).GET().build();
        return client.send(req, HttpResponse.BodyHandlers.ofString()).body();
    }

    private static String toHex(Color c) {
        return String.format("#%02x%02x%02x", (int)(c.getRed()*255), (int)(c.getGreen()*255), (int)(c.getBlue()*255));
    }

    // ========== GESTION ESPACES ==========
    public VBox getEspaceGestionView() {
        VBox root = new VBox(15);
        root.setPadding(new Insets(20));

        Label titre = new Label("Gestion des Espaces Agricoles");
        titre.setFont(Font.font("System", 20));

        // Form
        GridPane form = new GridPane();
        form.setHgap(10);
        form.setVgap(10);
        form.setStyle("-fx-background-color: #f5f5f5; -fx-padding: 15; -fx-border-radius: 8;");

        TextField nomF = new TextField(); nomF.setPromptText("Nom");
        TextField locF = new TextField(); locF.setPromptText("Localisation");
        TextField supF = new TextField(); supF.setPromptText("Superficie (ha)");
        TextField descF = new TextField(); descF.setPromptText("Description");

        ComboBox<String> actionBox = new ComboBox<>(
            FXCollections.observableArrayList("Créer", "Modifier", "Supprimer"));
        actionBox.setValue("Créer");
        TextField idF = new TextField(); idF.setPromptText("ID (pour modif/suppr)");
        Label status = new Label();

        Button execBtn = new Button("Exécuter");
        execBtn.setStyle("-fx-background-color: #2e7d32; -fx-text-fill: white; -fx-font-weight: bold;");

        execBtn.setOnAction(e -> {
            try {
                switch (actionBox.getValue()) {
                    case "Créer" -> {
                        String json = String.format(
                            "{\"nom\":\"%s\",\"localisation\":\"%s\",\"superficieTotale\":%s,\"description\":\"%s\",\"active\":true}",
                            nomF.getText(), locF.getText(), supF.getText(), descF.getText());
                        post("/espaces", json);
                        status.setText("Espace créé !");
                    }
                    case "Modifier" -> {
                        String json = String.format(
                            "{\"nom\":\"%s\",\"localisation\":\"%s\",\"superficieTotale\":%s,\"description\":\"%s\",\"active\":true}",
                            nomF.getText(), locF.getText(), supF.getText(), descF.getText());
                        put("/espaces/" + idF.getText(), json);
                        status.setText("Espace modifié !");
                    }
                    case "Supprimer" -> {
                        delete("/espaces/" + idF.getText());
                        status.setText("Espace supprimé !");
                    }
                }
            } catch (Exception ex) {
                status.setText("Erreur: " + ex.getMessage());
                status.setTextFill(Color.RED);
            }
        });

        Button loadBtn = new Button("Charger ID");
        loadBtn.setOnAction(e -> {
            try {
                HttpRequest req = auth().uri(URI.create(api + "/espaces/" + idF.getText())).GET().build();
                HttpResponse<String> resp = client.send(req, HttpResponse.BodyHandlers.ofString());
                status.setText(resp.body());
                status.setTextFill(Color.BLACK);
            } catch (Exception ex) {
                status.setText("Erreur: " + ex.getMessage());
            }
        });

        form.add(new Label("Action:"), 0, 0);
        form.add(actionBox, 1, 0);
        form.add(new Label("ID:"), 0, 1);
        form.add(idF, 1, 1);
        form.add(new Label("Nom:"), 0, 2);
        form.add(nomF, 1, 2);
        form.add(new Label("Localisation:"), 0, 3);
        form.add(locF, 1, 3);
        form.add(new Label("Superficie:"), 0, 4);
        form.add(supF, 1, 4);
        form.add(new Label("Description:"), 0, 5);
        form.add(descF, 1, 5);
        form.add(execBtn, 0, 6);
        form.add(loadBtn, 1, 6);
        form.add(status, 0, 7, 2, 1);

        // Table
        TableView<EspaceTable> table = new TableView<>();
        TableColumn<EspaceTable, Long> colId = new TableColumn<>("ID");
        colId.setCellValueFactory(new PropertyValueFactory<>("id"));
        TableColumn<EspaceTable, String> colNom = new TableColumn<>("Nom");
        colNom.setCellValueFactory(new PropertyValueFactory<>("nom"));
        TableColumn<EspaceTable, String> colLoc = new TableColumn<>("Localisation");
        colLoc.setCellValueFactory(new PropertyValueFactory<>("localisation"));
        TableColumn<EspaceTable, Double> colSup = new TableColumn<>("Superficie");
        colSup.setCellValueFactory(new PropertyValueFactory<>("superficieTotale"));
        table.getColumns().addAll(colId, colNom, colLoc, colSup);
        table.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY);
        table.setPrefHeight(250);

        Button refreshTable = new Button("Rafraîchir liste");
        refreshTable.setOnAction(e -> {
            try {
                HttpRequest req = auth().uri(URI.create(api + "/espaces")).GET().build();
                HttpResponse<String> resp = client.send(req, HttpResponse.BodyHandlers.ofString());
                String body = resp.body();
                if (body.equals("[]")) {
                    table.setItems(FXCollections.observableArrayList());
                    return;
                }
                ObservableList<EspaceTable> items = FXCollections.observableArrayList();
                body = body.substring(1, body.length() - 1);
                for (String part : body.split("\\},\\{")) {
                    part = part.replaceAll("[{}\"]", "");
                    String[] fields = part.split(",");
                    long id = 0; String nom = ""; String loc = ""; double sup = 0;
                    for (String f : fields) {
                        String[] kv = f.split(":", 2);
                        if (kv.length == 2) {
                            String k = kv[0].trim(), v = kv[1].trim();
                            switch (k) {
                                case "id" -> id = Long.parseLong(v);
                                case "nom" -> nom = v;
                                case "localisation" -> loc = v.equals("null") ? "" : v;
                                case "superficieTotale" -> sup = v.equals("null") ? 0 : Double.parseDouble(v);
                            }
                        }
                    }
                    items.add(new EspaceTable(id, nom, loc, sup));
                }
                table.setItems(items);
            } catch (Exception ex) {
                status.setText("Erreur chargement: " + ex.getMessage());
            }
        });

        // Cliquer sur une ligne remplit le formulaire
        table.getSelectionModel().selectedItemProperty().addListener((obs, old, val) -> {
            if (val != null) {
                idF.setText(String.valueOf(val.getId()));
                nomF.setText(val.getNom());
                locF.setText(val.getLocalisation());
                supF.setText(String.valueOf(val.getSuperficieTotale()));
                actionBox.setValue("Modifier");
            }
        });

        root.getChildren().addAll(titre, form, refreshTable, table);
        return root;
    }

    // ========== GESTION ZONES ==========
    public VBox getZoneGestionView() {
        VBox root = new VBox(15);
        root.setPadding(new Insets(20));

        Label titre = new Label("Gestion des Zones d'Irrigation");
        titre.setFont(Font.font("System", 20));

        GridPane form = new GridPane();
        form.setHgap(10);
        form.setVgap(10);
        form.setStyle("-fx-background-color: #f5f5f5; -fx-padding: 15; -fx-border-radius: 8;");

        TextField nomF = new TextField(); nomF.setPromptText("Nom");
        TextField supF = new TextField(); supF.setPromptText("Superficie (ha)");
        TextField cultureF = new TextField(); cultureF.setPromptText("Culture");
        TextField seuilF = new TextField(); seuilF.setPromptText("Seuil humidité (%)");
        TextField espaceIdF = new TextField(); espaceIdF.setPromptText("ID Espace");
        ComboBox<String> actionBox = new ComboBox<>(
            FXCollections.observableArrayList("Créer", "Modifier", "Supprimer"));
        actionBox.setValue("Créer");
        TextField idF = new TextField(); idF.setPromptText("ID (pour modif/suppr)");
        Label status = new Label();

        Button execBtn = new Button("Exécuter");
        execBtn.setStyle("-fx-background-color: #1565c0; -fx-text-fill: white; -fx-font-weight: bold;");

        execBtn.setOnAction(e -> {
            try {
                switch (actionBox.getValue()) {
                    case "Créer" -> {
                        String json = String.format(
                            "{\"nom\":\"%s\",\"superficie\":%s,\"culture\":\"%s\",\"seuilHumidite\":%s,\"active\":true}",
                            nomF.getText(), supF.getText(), cultureF.getText(), seuilF.getText());
                        post("/espaces/" + espaceIdF.getText() + "/zones", json);
                        status.setText("Zone créée !");
                    }
                    case "Modifier" -> {
                        String json = String.format(
                            "{\"nom\":\"%s\",\"superficie\":%s,\"culture\":\"%s\",\"seuilHumidite\":%s,\"espaceId\":%s,\"active\":true}",
                            nomF.getText(), supF.getText(), cultureF.getText(), seuilF.getText(), espaceIdF.getText());
                        put("/zones/" + idF.getText(), json);
                        status.setText("Zone modifiée !");
                    }
                    case "Supprimer" -> {
                        delete("/zones/" + idF.getText());
                        status.setText("Zone supprimée !");
                    }
                }
            } catch (Exception ex) {
                status.setText("Erreur: " + ex.getMessage());
                status.setTextFill(Color.RED);
            }
        });

        form.add(new Label("Action:"), 0, 0);
        form.add(actionBox, 1, 0);
        form.add(new Label("ID:"), 0, 1);
        form.add(idF, 1, 1);
        form.add(new Label("Nom:"), 0, 2);
        form.add(nomF, 1, 2);
        form.add(new Label("Superficie:"), 0, 3);
        form.add(supF, 1, 3);
        form.add(new Label("Culture:"), 0, 4);
        form.add(cultureF, 1, 4);
        form.add(new Label("Seuil:"), 0, 5);
        form.add(seuilF, 1, 5);
        form.add(new Label("Espace ID:"), 0, 6);
        form.add(espaceIdF, 1, 6);
        form.add(execBtn, 0, 7);
        form.add(status, 1, 7);

        // Tableau des zones
        TableView<ZoneTable> table = new TableView<>();
        TableColumn<ZoneTable, Long> colId = new TableColumn<>("ID");
        colId.setCellValueFactory(new PropertyValueFactory<>("id"));
        TableColumn<ZoneTable, String> colNom = new TableColumn<>("Nom");
        colNom.setCellValueFactory(new PropertyValueFactory<>("nom"));
        TableColumn<ZoneTable, Double> colSup = new TableColumn<>("Superficie");
        colSup.setCellValueFactory(new PropertyValueFactory<>("superficie"));
        TableColumn<ZoneTable, String> colCulture = new TableColumn<>("Culture");
        colCulture.setCellValueFactory(new PropertyValueFactory<>("culture"));
        TableColumn<ZoneTable, Double> colSeuil = new TableColumn<>("Seuil %");
        colSeuil.setCellValueFactory(new PropertyValueFactory<>("seuilHumidite"));
        TableColumn<ZoneTable, Long> colEspace = new TableColumn<>("Espace ID");
        colEspace.setCellValueFactory(new PropertyValueFactory<>("espaceId"));
        TableColumn<ZoneTable, Double> colHum = new TableColumn<>("Humidité");
        colHum.setCellValueFactory(new PropertyValueFactory<>("derniereHumidite"));
        table.getColumns().addAll(colId, colNom, colSup, colCulture, colSeuil, colEspace, colHum);
        table.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY);
        table.setPrefHeight(250);

        Button refreshTable = new Button("Rafraîchir liste");
        refreshTable.setOnAction(e -> {
            try {
                String body = get(api + "/zones");
                if (body.equals("[]")) {
                    table.setItems(FXCollections.observableArrayList());
                    status.setText("Aucune zone trouvée");
                    return;
                }
                ObservableList<ZoneTable> items = FXCollections.observableArrayList();
                body = body.substring(1, body.length() - 1);
                for (String part : body.split("\\},\\{")) {
                    part = part.replaceAll("[{}\"]", "");
                    String[] fields = part.split(",");
                    long id = 0; String nom = ""; double sup = 0; String culture = "";
                    double seuil = 0; long espaceId = 0; double hum = -1;
                    for (String f : fields) {
                        String[] kv = f.split(":", 2);
                        if (kv.length == 2) {
                            String k = kv[0].trim(), v = kv[1].trim();
                            switch (k) {
                                case "id" -> id = Long.parseLong(v);
                                case "nom" -> nom = v;
                                case "superficie" -> sup = v.equals("null") ? 0 : Double.parseDouble(v);
                                case "culture" -> culture = v.equals("null") ? "" : v;
                                case "seuilHumidite" -> seuil = v.equals("null") ? 0 : Double.parseDouble(v);
                                case "espaceId" -> espaceId = v.equals("null") ? 0 : Long.parseLong(v);
                                case "derniereHumidite" -> hum = v.equals("null") ? -1 : Double.parseDouble(v);
                            }
                        }
                    }
                    items.add(new ZoneTable(id, nom, sup, culture, seuil, espaceId, hum));
                }
                table.setItems(items);
                status.setText(items.size() + " zone(s) chargée(s)");
            } catch (Exception ex) {
                status.setText("Erreur chargement: " + ex.getMessage());
            }
        });

        table.getSelectionModel().selectedItemProperty().addListener((obs, old, val) -> {
            if (val != null) {
                idF.setText(String.valueOf(val.getId()));
                nomF.setText(val.getNom());
                supF.setText(String.valueOf(val.getSuperficie()));
                cultureF.setText(val.getCulture());
                seuilF.setText(String.valueOf(val.getSeuilHumidite()));
                espaceIdF.setText(String.valueOf(val.getEspaceId()));
                actionBox.setValue("Modifier");
            }
        });

        root.getChildren().addAll(titre, form, refreshTable, table);
        return root;
    }

    // ========== GESTION UTILISATEURS ==========
    public VBox getUserGestionView() {
        VBox root = new VBox(15);
        root.setPadding(new Insets(20));

        Label titre = new Label("Gestion des Utilisateurs");
        titre.setFont(Font.font("System", 20));

        GridPane form = new GridPane();
        form.setHgap(10);
        form.setVgap(10);
        form.setStyle("-fx-background-color: #f5f5f5; -fx-padding: 15; -fx-border-radius: 8;");

        TextField emailF = new TextField(); emailF.setPromptText("Email");
        TextField mdpF = new TextField(); mdpF.setPromptText("Mot de passe (vide = inchangé)");
        TextField nomF = new TextField(); nomF.setPromptText("Nom complet");
        ComboBox<String> roleBox = new ComboBox<>(
            FXCollections.observableArrayList("ADMIN", "AGRICULTEUR", "TECHNICIEN"));
        roleBox.setValue("AGRICULTEUR");
        ComboBox<String> actionBox = new ComboBox<>(
            FXCollections.observableArrayList("Créer", "Modifier", "Supprimer"));
        actionBox.setValue("Créer");
        TextField idF = new TextField(); idF.setPromptText("ID (pour modif/suppr)");
        Label status = new Label();

        Button execBtn = new Button("Exécuter");
        execBtn.setStyle("-fx-background-color: #6a1b9a; -fx-text-fill: white; -fx-font-weight: bold;");

        execBtn.setOnAction(e -> {
            try {
                switch (actionBox.getValue()) {
                    case "Créer" -> {
                        String json = String.format(
                            "{\"email\":\"%s\",\"motDePasse\":\"%s\",\"nom\":\"%s\",\"role\":\"%s\"}",
                            emailF.getText(), mdpF.getText(), nomF.getText(), roleBox.getValue());
                        post("/auth/inscription", json);
                        status.setText("Utilisateur créé !");
                    }
                    case "Modifier" -> {
                        String mdp = mdpF.getText().isBlank() ? "" : mdpF.getText();
                        String json = String.format(
                            "{\"email\":\"%s\",\"motDePasse\":\"%s\",\"nom\":\"%s\",\"role\":\"%s\"}",
                            emailF.getText(), mdp, nomF.getText(), roleBox.getValue());
                        put("/utilisateurs/" + idF.getText(), json);
                        status.setText("Utilisateur modifié !");
                    }
                    case "Supprimer" -> {
                        delete("/utilisateurs/" + idF.getText());
                        status.setText("Utilisateur supprimé !");
                    }
                }
                status.setTextFill(Color.GREEN);
            } catch (Exception ex) {
                status.setText("Erreur: " + ex.getMessage());
                status.setTextFill(Color.RED);
            }
        });

        form.add(new Label("Action:"), 0, 0);
        form.add(actionBox, 1, 0);
        form.add(new Label("ID:"), 0, 1);
        form.add(idF, 1, 1);
        form.add(new Label("Email:"), 0, 2);
        form.add(emailF, 1, 2);
        form.add(new Label("Mot de passe:"), 0, 3);
        form.add(mdpF, 1, 3);
        form.add(new Label("Nom:"), 0, 4);
        form.add(nomF, 1, 4);
        form.add(new Label("Rôle:"), 0, 5);
        form.add(roleBox, 1, 5);
        form.add(execBtn, 0, 6);
        form.add(status, 1, 6);

        // Tableau
        TableView<UtilisateurTable> table = new TableView<>();
        TableColumn<UtilisateurTable, Long> colId = new TableColumn<>("ID");
        colId.setCellValueFactory(new PropertyValueFactory<>("id"));
        TableColumn<UtilisateurTable, String> colEmail = new TableColumn<>("Email");
        colEmail.setCellValueFactory(new PropertyValueFactory<>("email"));
        TableColumn<UtilisateurTable, String> colNom = new TableColumn<>("Nom");
        colNom.setCellValueFactory(new PropertyValueFactory<>("nom"));
        TableColumn<UtilisateurTable, String> colRole = new TableColumn<>("Rôle");
        colRole.setCellValueFactory(new PropertyValueFactory<>("role"));
        table.getColumns().addAll(colId, colEmail, colNom, colRole);
        table.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY);
        table.setPrefHeight(250);

        Button refreshTable = new Button("Rafraîchir liste");
        refreshTable.setOnAction(e -> {
            try {
                String body = get(api + "/utilisateurs");
                if (body.equals("[]")) {
                    table.setItems(FXCollections.observableArrayList());
                    status.setText("Aucun utilisateur");
                    return;
                }
                ObservableList<UtilisateurTable> items = FXCollections.observableArrayList();
                body = body.substring(1, body.length() - 1);
                for (String part : body.split("\\},\\{")) {
                    part = part.replaceAll("[{}\"]", "");
                    String[] fields = part.split(",");
                    long id = 0; String email = ""; String nom = ""; String role = "";
                    for (String f : fields) {
                        String[] kv = f.split(":", 2);
                        if (kv.length == 2) {
                            String k = kv[0].trim(), v = kv[1].trim();
                            switch (k) {
                                case "id" -> id = Long.parseLong(v);
                                case "email" -> email = v;
                                case "nom" -> nom = v;
                                case "role" -> role = v;
                            }
                        }
                    }
                    items.add(new UtilisateurTable(id, email, nom, role));
                }
                table.setItems(items);
                status.setText(items.size() + " utilisateur(s)");
            } catch (Exception ex) {
                status.setText("Erreur: " + ex.getMessage());
            }
        });

        table.getSelectionModel().selectedItemProperty().addListener((obs, old, val) -> {
            if (val != null) {
                idF.setText(String.valueOf(val.getId()));
                emailF.setText(val.getEmail());
                nomF.setText(val.getNom());
                roleBox.setValue(val.getRole());
                mdpF.clear();
                actionBox.setValue("Modifier");
            }
        });

        root.getChildren().addAll(titre, form, refreshTable, table);
        return root;
    }

    // ========== RAPPORTS ==========
    public VBox getRapportView() {
        VBox root = new VBox(15);
        root.setPadding(new Insets(20));

        Label titre = new Label("Rapports et Alertes");
        titre.setFont(Font.font("System", 20));

        // Section alertes
        TitledPane alertPane = new TitledPane("Alertes d'Irrigation", new Label("Les alertes seront envoyées par email lorsque l'humidité passe sous le seuil défini pour chaque zone.\n\nFonctionnalité à connecter à un service SMTP."));
        alertPane.setExpanded(true);

        // Section export
        TitledPane exportPane = new TitledPane("Export de Données", getExportView());
        exportPane.setExpanded(false);

        // Section historique
        TitledPane histPane = new TitledPane("Historique des Irrigations", getHistoriqueView());
        histPane.setExpanded(false);

        root.getChildren().addAll(titre, alertPane, exportPane, histPane);
        return root;
    }

    private VBox getExportView() {
        VBox v = new VBox(10);
        v.setPadding(new Insets(10));

        TextField zoneExportId = new TextField();
        zoneExportId.setPromptText("ID de la zone");
        Button exportCSV = new Button("Exporter les mesures (CSV)");
        Label statusExport = new Label();

        exportCSV.setOnAction(e -> {
            FileChooser fc = new FileChooser();
            fc.setTitle("Enregistrer l'export CSV");
            fc.getExtensionFilters().add(new FileChooser.ExtensionFilter("Fichier CSV", "*.csv"));
            fc.setInitialFileName("mesures_zone_" + zoneExportId.getText() + ".csv");
            File file = fc.showSaveDialog(stage);
            if (file == null) return;

            try {
                String body = get(api + "/mesures/" + zoneExportId.getText());
                StringBuilder csv = new StringBuilder("zoneId,zoneNom,humidite,temperature,conductivite,timestamp\n");

                if (body.length() > 2) {
                    String inner = body.substring(1, body.length() - 1);
                    for (String part : inner.split("\\},\\{")) {
                        part = part.replaceAll("[{}\"]", "");
                        String[] fields = part.split(",");
                        String zid = "", znom = "", hum = "", temp = "", cond = "", ts = "";
                        for (String f : fields) {
                            String[] kv = f.split(":", 2);
                            if (kv.length == 2) {
                                String k = kv[0].trim(), val = kv[1].trim();
                                switch (k) {
                                    case "zoneId" -> zid = val;
                                    case "zoneNom" -> znom = val;
                                    case "humidite" -> hum = val;
                                    case "temperature" -> temp = val;
                                    case "conductivite" -> cond = val;
                                    case "timestamp" -> ts = val;
                                }
                            }
                        }
                        csv.append(zid).append(",").append(znom).append(",").append(hum)
                           .append(",").append(temp).append(",").append(cond).append(",").append(ts).append("\n");
                    }
                }

                try (FileWriter fw = new FileWriter(file)) {
                    fw.write(csv.toString());
                }
                statusExport.setText("Exporté: " + file.getAbsolutePath() + " (" + csv.length() + " octets)");
                statusExport.setTextFill(Color.GREEN);
            } catch (Exception ex) {
                statusExport.setText("Erreur: " + ex.getMessage());
                statusExport.setTextFill(Color.RED);
            }
        });

        HBox controls = new HBox(10, new Label("ID Zone:"), zoneExportId, exportCSV);
        v.getChildren().addAll(new Label("Export des données capteurs au format CSV :"), controls, statusExport);
        return v;
    }

    private VBox getHistoriqueView() {
        VBox v = new VBox(10);
        v.setPadding(new Insets(10));

        TextField zoneIdF = new TextField();
        zoneIdF.setPromptText("ID de la zone");
        Button chargerBtn = new Button("Charger historique");
        TextArea area = new TextArea();
        area.setPrefHeight(300);
        area.setEditable(false);

        chargerBtn.setOnAction(e -> {
            try {
                HttpRequest req = auth()
                    .uri(URI.create(api + "/irrigation/historique/" + zoneIdF.getText()))
                    .GET().build();
                HttpResponse<String> resp = client.send(req, HttpResponse.BodyHandlers.ofString());
                area.setText(resp.body());
            } catch (Exception ex) {
                area.setText("Erreur: " + ex.getMessage());
            }
        });

        HBox controls = new HBox(10, new Label("Zone ID:"), zoneIdF, chargerBtn);
        v.getChildren().addAll(controls, area);
        return v;
    }

    // ========== HTTP HELPERS ==========
    private void post(String path, String json) throws Exception {
        HttpRequest req = auth()
            .uri(URI.create(api + path))
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build();
        client.send(req, HttpResponse.BodyHandlers.ofString());
    }

    private void put(String path, String json) throws Exception {
        HttpRequest req = auth()
            .uri(URI.create(api + path))
            .PUT(HttpRequest.BodyPublishers.ofString(json))
            .build();
        client.send(req, HttpResponse.BodyHandlers.ofString());
    }

    private void delete(String path) throws Exception {
        HttpRequest req = auth()
            .uri(URI.create(api + path))
            .DELETE()
            .build();
        client.send(req, HttpResponse.BodyHandlers.ofString());
    }

    // ========== TABLE MODELS ==========
    public static class ZoneTable {
        private final long id;
        private final String nom;
        private final double superficie;
        private final String culture;
        private final double seuilHumidite;
        private final long espaceId;
        private final double derniereHumidite;

        public ZoneTable(long id, String nom, double superficie, String culture, double seuilHumidite, long espaceId, double derniereHumidite) {
            this.id = id; this.nom = nom; this.superficie = superficie; this.culture = culture;
            this.seuilHumidite = seuilHumidite; this.espaceId = espaceId; this.derniereHumidite = derniereHumidite;
        }
        public long getId() { return id; }
        public String getNom() { return nom; }
        public double getSuperficie() { return superficie; }
        public String getCulture() { return culture; }
        public double getSeuilHumidite() { return seuilHumidite; }
        public long getEspaceId() { return espaceId; }
        public double getDerniereHumidite() { return derniereHumidite; }
    }

    public static class UtilisateurTable {
        private final long id;
        private final String email;
        private final String nom;
        private final String role;

        public UtilisateurTable(long id, String email, String nom, String role) {
            this.id = id; this.email = email; this.nom = nom; this.role = role;
        }
        public long getId() { return id; }
        public String getEmail() { return email; }
        public String getNom() { return nom; }
        public String getRole() { return role; }
    }

    public static class EspaceTable {
        private final long id;
        private final String nom;
        private final String localisation;
        private final double superficieTotale;

        public EspaceTable(long id, String nom, String localisation, double superficieTotale) {
            this.id = id;
            this.nom = nom;
            this.localisation = localisation;
            this.superficieTotale = superficieTotale;
        }

        public long getId() { return id; }
        public String getNom() { return nom; }
        public String getLocalisation() { return localisation; }
        public double getSuperficieTotale() { return superficieTotale; }
    }
}
