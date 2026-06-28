#!/usr/bin/env python3
"""Seed MySQL with comprehensive agronomic plant database.

Usage:
    python scripts/seed_plantes.py
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

MYSQL_USER = "agricol"
MYSQL_PASSWORD = "agricol_secret"
MYSQL_HOST = "localhost"
MYSQL_DB = "agricol"

try:
    import pymysql
except ImportError:
    print("pip install pymysql")
    sys.exit(1)

conn = pymysql.connect(
    host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD,
    database=MYSQL_DB, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
)
cur = conn.cursor()

# =========================================================
# DATA
# =========================================================

categories = [
    (1, "Arbres Fruitiers", "Arbres produisant des fruits comestibles, cultures perennes"),
    (2, "Cereales", "Graminees cultivees pour leurs grains (alimentation humaine et animale)"),
    (3, "Legumineuses", "Plantes fixatrices d'azote, riches en proteines"),
    (4, "Maraichage", "Legumes cultives en plein champ ou sous serre"),
    (5, "Plantes Fourrageres", "Cultures destinees a l'alimentation du betail"),
    (6, "Plantes Industrielles", "Cultures destinees a la transformation industrielle"),
    (7, "Aromatiques & Medicinales", "Plantes a usage culinaire, medicinal ou aromatique"),
    (8, "Oleagineux", "Cultures riches en huile vegetale"),
    (9, "Cultures de Couverture", "Plantes pour couvrir et proteger le sol"),
    (10, "Epices", "Plantes cultivees pour leurs epices (graines, ecorces, racines)"),
]

familles = [
    (1, "Rosaceae", "Famille des rosiers - pommes, poires, peches, cerises"),
    (2, "Oleaceae", "Famille de l'olivier et du fremble"),
    (3, "Rutaceae", "Famille des agrumes - orangers, citronniers"),
    (4, "Poaceae", "Famille des graminees - ble, riz, mais, orge"),
    (5, "Fabaceae", "Famille des legumineuses - pois, haricots, luzerne"),
    (6, "Solanaceae", "Famille des solanacees - tomate, pomme de terre"),
    (7, "Cucurbitaceae", "Famille des courges, melons, concombres"),
    (8, "Alliaceae", "Famille des oignons, ails, poireaux"),
    (9, "Apiaceae", "Famille des carottes, persil, fenouil"),
    (10, "Brassicaceae", "Famille des choux, navets, moutarde"),
    (11, "Asteraceae", "Famille des tournesols, laitues, artichauts"),
    (12, "Lamiaceae", "Famille des menthes, romarin, thym, basilic"),
    (13, "Chenopodiaceae", "Famille des betteraves, epinards"),
    (14, "Linaceae", "Famille du lin"),
    (15, "Malvaceae", "Famille du coton et du cacao"),
    (16, "Euphorbiaceae", "Famille du manioc et de l'hevea"),
    (17, "Convolvulaceae", "Famille de la patate douce"),
    (18, "Musaceae", "Famille du bananier"),
    (19, "Vitaceae", "Famille de la vigne"),
    (20, "Anacardiaceae", "Famille du pistachier et du manguier"),
    (21, "Lauraceae", "Famille de l'avocatier"),
    (22, "Arecaceae", "Famille des palmiers - dattier, cocotier"),
    (23, "Moraceae", "Famille du murier et du figuier"),
    (24, "Polygonaceae", "Famille du sarrasin et de la rhubarbe"),
    (25, "Pedaliaceae", "Famille du sesame"),
]

plantes = [
    # --- ARBRES FRUITIERS ---
    (1, "Olivier", "Olea europaea", 1, 2, "perenne", "Arbre emblematique du bassin mediterraneen, oleagineux, fruit=l'olive"),
    (2, "Oranger", "Citrus sinensis", 1, 3, "perenne", "Agrume majeur, fruit=juteux et sucre"),
    (3, "Citronnier", "Citrus limon", 1, 3, "perenne", "Agrume acide, usage culinaire et medicinal"),
    (4, "Pommier", "Malus domestica", 1, 1, "perenne", "Arbre fruitier le plus cultive en zone temperee"),
    (5, "Poirier", "Pyrus communis", 1, 1, "perenne", "Arbre fruitier a pepins, cousin du pommier"),
    (6, "Peche", "Prunus persica", 1, 1, "perenne", "Arbre fruitier a noyau, peau duveteuse"),
    (7, "Abricotier", "Prunus armeniaca", 1, 1, "perenne", "Petit arbre fruitier a noyau, fruits orange"),
    (8, "Cerisier", "Prunus avium", 1, 1, "perenne", "Cerises douces, arbre vigoureux"),
    (9, "Pommier Grany", "Prunus domestica", 1, 1, "perenne", "Prunier europeen, prunes de table"),
    (10, "Amandier", "Prunus dulcis", 1, 1, "perenne", "Amandes comestibles, fleurit tres tot"),
    (11, "Noyer", "Juglans regia", 1, 1, "perenne", "Noix, bois de qualite"),
    (12, "Figuier", "Ficus carica", 1, 23, "perenne", "Figues fraiches et sechees"),
    (13, "Grenadier", "Punica granatum", 1, 1, "perenne", "Grenade, riche en antioxydants"),
    (14, "Kaki", "Diospyros kaki", 1, 1, "perenne", "Fruit plaqueminier, kaki"),
    (15, "Avocatier", "Persea americana", 1, 21, "perenne", "Avocat, fruit oleagineux tropical"),
    (16, "Manguier", "Mangifera indica", 1, 20, "perenne", "Mangue, fruit tropical roi"),
    (17, "Bananier", "Musa acuminata", 1, 18, "perenne", "Banane, fruit tropical de base"),
    (18, "Dattier", "Phoenix dactylifera", 1, 22, "perenne", "Dattes, palmier des oasis"),
    (19, "Cocotier", "Cocos nucifera", 1, 22, "perenne", "Noix de coco, huile, eau"),
    (20, "Pistachier", "Pistacia vera", 1, 20, "perenne", "Pistache, fruit sec oleagineux"),
    (21, "Murier", "Morus nigra", 1, 23, "perenne", "Mures, feuilles pour vers a soie"),

    # --- CEREALES ---
    (22, "Ble tendre", "Triticum aestivum", 2, 4, "annuel", "Ble a pain, culture cerealiere principale en Europe"),
    (23, "Ble dur", "Triticum durum", 2, 4, "annuel", "Ble a semoule et pates"),
    (24, "Riz", "Oryza sativa", 2, 4, "annuel", "Cereale de base en Asie, culture submergee"),
    (25, "Mais", "Zea mays", 2, 4, "annuel", "Cereale fourragere et alimentaire, rendement eleve"),
    (26, "Orge", "Hordeum vulgare", 2, 4, "annuel", "Brasserie et alimentation animale"),
    (27, "Sorgho", "Sorghum bicolor", 2, 4, "annuel", "Cereale resiliente a la secheresse"),
    (28, "Avoine", "Avena sativa", 2, 4, "annuel", "Cereale pour alimentation humaine et chevaline"),
    (29, "Seigle", "Secale cereale", 2, 4, "annuel", "Cereale rustique, pain noir"),
    (30, "Millet", "Pennisetum glaucum", 2, 4, "annuel", "Cereale mineure, tres resistante a la secheresse"),
    (31, "Triticale", "x Triticosecale", 2, 4, "annuel", "Hybride ble-seigle, fourrager et alimentaire"),
    (32, "Sarrasin", "Fagopyrum esculentum", 2, 24, "annuel", "Fausse cereale, sans gluten"),

    # --- LEGUMINEUSES ---
    (33, "Pois chiche", "Cicer arietinum", 3, 5, "annuel", "Legumineuse proteique majeure, cuisine orientale"),
    (34, "Lentille", "Lens culinaris", 3, 5, "annuel", "Petite legumineuse, riche en fer et proteines"),
    (35, "Soja", "Glycine max", 3, 5, "annuel", "Legumineuse oleagineuse, proteine vegetale"),
    (36, "Feverole", "Vicia faba", 3, 5, "annuel", "Grosse feve, alimentation humaine et animale"),
    (37, "Pois proteagineux", "Pisum sativum", 3, 5, "annuel", "Pois cultive pour les graines seches"),
    (38, "Haricot sec", "Phaseolus vulgaris", 3, 5, "annuel", "Haricots pour grains secs (coco, lingot, rouge)"),
    (39, "Lupin", "Lupinus albus", 3, 5, "annuel", "Legumineuse a graines proteiques, ammendante"),
    (40, "Fenugrec", "Trigonella foenum-graecum", 3, 5, "annuel", "Epice et legumineuse fourragere"),
    (41, "Arachide", "Arachis hypogaea", 3, 5, "annuel", "Cacahuete, oleagineuse et legumineuse"),
    (42, "Pois cajan", "Cajanus cajan", 3, 5, "vivace", "Pois d'Angole, legumineuse tropicale"),
    (43, "Niobe", "Vigna unguiculata", 3, 5, "annuel", "Niebe, legumineuse africaine resistante"),

    # --- MARAICHAGE ---
    (44, "Tomate", "Solanum lycopersicum", 4, 6, "annuel", "Legume-fruit, culture mondiale"),
    (45, "Pomme de terre", "Solanum tuberosum", 4, 6, "annuel", "Tubercule, 4e culture alimentaire mondiale"),
    (46, "Oignon", "Allium cepa", 4, 8, "annuel", "Bulbe condimentaire de base"),
    (47, "Carotte", "Daucus carota", 4, 9, "annuel", "Racine orange riche en carotene"),
    (48, "Laitue", "Lactuca sativa", 4, 11, "annuel", "Salade feuilles"),
    (49, "Chou pomme", "Brassica oleracea", 4, 10, "annuel", "Chou cabus, chou rouge"),
    (50, "Concombre", "Cucumis sativus", 4, 7, "annuel", "Legume-fruit d'ete, frais"),
    (51, "Courgette", "Cucurbita pepo", 4, 7, "annuel", "Courge d'ete"),
    (52, "Potiron", "Cucurbita maxima", 4, 7, "annuel", "Courge d'hiver, potiron"),
    (53, "Poivron", "Capsicum annuum", 4, 6, "annuel", "Piment doux, legume-fruit"),
    (54, "Aubergine", "Solanum melongena", 4, 6, "annuel", "Legume-fruit mediterraneen"),
    (55, "Haricot vert", "Phaseolus vulgaris", 4, 5, "annuel", "Gousse verte immature"),
    (56, "Petit pois", "Pisum sativum", 4, 5, "annuel", "Pois frais, legume printanier"),
    (57, "Epinard", "Spinacia oleracea", 4, 13, "annuel", "Feuille verte riche en fer"),
    (58, "Betterave rouge", "Beta vulgaris", 4, 13, "annuel", "Racine rouge sucre"),
    (59, "Artichaut", "Cynara cardunculus", 4, 11, "vivace", "Capitule floral comestible"),
    (60, "Fraisier", "Fragaria x ananassa", 4, 1, "vivace", "Fraise, fruit rouge"),
    (61, "Pastque", "Citrullus lanatus", 4, 7, "annuel", "Gros fruit estival rafraichissant"),
    (62, "Melon", "Cucumis melo", 4, 7, "annuel", "Melon charentais, galia, cantaloup"),
    (63, "Poireau", "Allium porrum", 4, 8, "annuel", "Legume bulbe allonge d'hiver"),
    (64, "Ail", "Allium sativum", 4, 8, "annuel", "Bulbe condimentaire medicinal"),
    (65, "Radis", "Raphanus sativus", 4, 10, "annuel", "Petite racine croquante, cycle court"),
    (66, "Echalote", "Allium ascalonicum", 4, 8, "annuel", "Bulbe fin condimentaire"),
    (67, "Chou-fleur", "Brassica oleracea", 4, 10, "annuel", "Inflorescence blanche comestible"),
    (68, "Brocoli", "Brassica oleracea", 4, 10, "annuel", "Tige et inflorescence verte"),
    (69, "Navet", "Brassica rapa", 4, 10, "annuel", "Racine blanche ronde"),
    (70, "Celri", "Apium graveolens", 4, 9, "annuel", "Tige croquante, branche de celeri"),
    (71, "Fenouil", "Foeniculum vulgare", 4, 9, "annuel", "Bulbe anise, cru ou cuit"),
    (72, "Mache", "Valerianella locusta", 4, 9, "annuel", "Salade d'hiver, petite feuille"),
    (73, "Patate douce", "Ipomoea batatas", 4, 17, "annuel", "Tubercule sucre tropical"),

    # --- FOURRAGERES ---
    (74, "Luzerne", "Medicago sativa", 5, 5, "vivace", "Reine des fourrageres, riche en proteines"),
    (75, "Trefl violet", "Trifolium pratense", 5, 5, "vivace", "Legumineuse fourragere"),
    (76, "Trefl blanc", "Trifolium repens", 5, 5, "vivace", "Paturage, couvert vegetal"),
    (77, "Ray-grass anglais", "Lolium perenne", 5, 4, "vivace", "Graminee fourragere de base"),
    (78, "Ray-grass italien", "Lolium multiflorum", 5, 4, "annuel", "Fourrage temporaire productif"),
    (79, "Dactyle", "Dactylis glomerata", 5, 4, "vivace", "Graminee fourragere persistante"),
    (80, "Fetuque elevee", "Festuca arundinacea", 5, 4, "vivace", "Graminee robuste, tolerante secheresse"),
    (81, "Brome", "Bromus catharticus", 5, 4, "annuel", "Graminee fourragere annuelle"),
    (82, "Lotier", "Lotus corniculatus", 5, 5, "vivace", "Legumineuse fourragere, sols pauvres"),
    (83, "Sainfoin", "Onobrychis viciifolia", 5, 5, "vivace", "Legumineuse fourragere, sans metorisation"),
    (84, "Vesce", "Vicia sativa", 5, 5, "annuel", "Fourrage et engrais vert"),
    (85, "Chou fourrager", "Brassica oleracea", 5, 10, "annuel", "Fourrage d'hiver pour betail"),
    (86, "Betterave fourragere", "Beta vulgaris", 5, 13, "annuel", "Racine fourragere energique"),

    # --- INDUSTRIELLES ---
    (87, "Coton", "Gossypium hirsutum", 6, 15, "annuel", "Fibre textile, huile de coton"),
    (88, "Canne sucre", "Saccharum officinarum", 6, 4, "vivace", "Sucre, bioethanol"),
    (89, "Betterave sucriere", "Beta vulgaris", 6, 13, "annuel", "Sucre de betterave"),
    (90, "Tabac", "Nicotiana tabacum", 6, 6, "annuel", "Feuilles pour cigarette"),
    (91, "Chanvre", "Cannabis sativa", 6, 6, "annuel", "Fibre, papier, huile, CBD"),
    (92, "Lin textile", "Linum usitatissimum", 6, 14, "annuel", "Fibre textile, graine oleagineuse"),
    (93, "Hvea", "Hevea brasiliensis", 6, 16, "perenne", "Caoutchouc naturel, latex"),
    (94, "Cafier", "Coffea arabica", 6, 1, "perenne", "Cafe, boisson mondiale"),
    (95, "Cacaoyer", "Theobroma cacao", 6, 15, "perenne", "Chocolat"),
    (96, "Theier", "Camellia sinensis", 6, 1, "perenne", "The"),
    (97, "Vigne", "Vitis vinifera", 6, 19, "perenne", "Vin, raisin de table"),
    (98, "Houblon", "Humulus lupulus", 6, 6, "vivace", "Brasserie, biere"),
    (99, "Menthe poivree", "Mentha x piperita", 7, 12, "vivace", "Huile essentielle, confiserie"),
    (100, "Manioc", "Manihot esculenta", 6, 16, "annuel", "Racine amylacee, tapioca"),

    # --- AROMATIQUES ---
    (101, "Menthe verte", "Mentha spicata", 7, 12, "vivace", "The a la menthe, cuisine orientale"),
    (102, "Romarin", "Rosmarinus officinalis", 7, 12, "vivace", "Arbrisseau aromatique mediterraneen"),
    (103, "Thym", "Thymus vulgaris", 7, 12, "vivace", "Herbe aromatique, antiseptique"),
    (104, "Basilic", "Ocimum basilicum", 7, 12, "annuel", "Pesto, cuisine italienne"),
    (105, "Persil", "Petroselinum crispum", 7, 9, "annuel", "Herbe aromatique de base"),
    (106, "Ciboulette", "Allium schoenoprasum", 7, 8, "vivace", "Fines herbes"),
    (107, "Coriandre", "Coriandrum sativum", 7, 9, "annuel", "Graines epice, feuilles herbe"),
    (108, "Laurier", "Laurus nobilis", 7, 21, "perenne", "Feuille aromatique pour bouillon"),
    (109, "Origan", "Origanum vulgare", 7, 12, "vivace", "Pizza, herbes de Provence"),
    (110, "Sauge", "Salvia officinalis", 7, 12, "vivace", "Herbe medicinale et culinaire"),
    (111, "Estragon", "Artemisia dracunculus", 7, 11, "vivace", "Vinaigre, sauce bearnaise"),
    (112, "Aneth", "Anethum graveolens", 7, 9, "annuel", "Poisson, cornichons"),
    (113, "Lavande", "Lavandula angustifolia", 7, 12, "vivace", "Parfum, huile essentielle"),
    (114, "Verveine", "Aloysia citrodora", 7, 9, "vivace", "Tisane citronnee"),
    (115, "Camomille", "Matricaria chamomilla", 7, 11, "annuel", "Tisane apaisante"),

    # --- OLEAGINEUX ---
    (116, "Tournesol", "Helianthus annuus", 8, 11, "annuel", "Huile oleique et lineolique, graines"),
    (117, "Colza", "Brassica napus", 8, 10, "annuel", "Huile vegetale, biocarburant"),
    (118, "Lin oleagineux", "Linum usitatissimum", 8, 14, "annuel", "Huile de lin riche en omega-3"),
    (119, "Sesame", "Sesamum indicum", 8, 25, "annuel", "Graines oleagineuses, tahini, huile"),
    (120, "Palmier a huile", "Elaeis guineensis", 8, 22, "perenne", "Huile de palme, oleagineuse tropicale"),
    (121, "Carthame", "Carthamus tinctorius", 8, 11, "annuel", "Huile de carthame, colorant alimentaire"),

    # --- COUVERTURE ---
    (122, "Moutarde blanche", "Sinapis alba", 9, 10, "annuel", "Engrais vert, biofumigation"),
    (123, "Phacelie", "Phacelia tanacetifolia", 9, 9, "annuel", "Mellifere, couvert structurant"),
    (124, "Seigle fourrager", "Secale cereale", 9, 4, "annuel", "Couvert hivernal, structurant"),
    (125, "Avoine rude", "Avena strigosa", 9, 4, "annuel", "Couvert estival rapide"),
    (126, "Trefl incarnat", "Trifolium incarnatum", 9, 5, "annuel", "Couvert fixateur d'azote"),
    (127, "Radis fourrager", "Raphanus sativus", 9, 10, "annuel", "Couvert a pivot, structurant"),
    (128, "Luzerne annuelle", "Medicago truncatula", 9, 5, "annuel", "Couvert fixateur d'azote court"),

    # --- EPICES ---
    (129, "Poivre noir", "Piper nigrum", 10, 6, "vivace", "Liane a poivre, epice roi"),
    (130, "Safran", "Crocus sativus", 10, 9, "vivace", "Epice la plus chere du monde"),
    (131, "Vanille", "Vanilla planifolia", 10, 1, "vivace", "Gousse d'orchidee vanillee"),
    (132, "Cannelle", "Cinnamomum verum", 10, 21, "perenne", "Ecorce aromatique"),
    (133, "Muscade", "Myristica fragrans", 10, 23, "perenne", "Noix de muscade"),
    (134, "Gingembre", "Zingiber officinale", 10, 6, "vivace", "Rhizome epic"),
    (135, "Curcuma", "Curcuma longa", 10, 6, "vivace", "Rhizome jaune, curcumine"),
    (136, "Piment", "Capsicum frutescens", 10, 6, "annuel", "Piment fort, capsaicine"),
    (137, "Cumin", "Cuminum cyminum", 10, 9, "annuel", "Graine epic, cuisine orientale"),
    (138, "Carvi", "Carum carvi", 10, 9, "annuel", "Graine epic, pain et fromage"),
]

varietes = [
    (1, 1, "Picholine", "faible", "Calcaire", 50.00, "Vert de gris", "France", "Huile et verte de table"),
    (2, 1, "Lucques", "faible", "Argilo-calcaire", 45.00, "Tavelure", "France", "Verte de table"),
    (3, 1, "Aglandau", "faible", "Calcaire", 40.00, "Mouche olive", "France", "Huile AOC"),
    (4, 1, "Arbequina", "faible", "Tous sols", 60.00, "Froid", "Espagne", "Huile fruitée"),
    (5, 1, "Koroneiki", "faible", "Sols pauvres", 55.00, "Verticillium", "Grece", "Huile intense"),
    (6, 1, "Chemlali", "faible", "Sableux", 65.00, "Secheresse", "Tunisie", "Huile douce"),
    (7, 2, "Valencia", "moyen", "Sableux", 70.00, "Chancre", "Espagne", "Jus et table"),
    (8, 2, "Navel Washington", "moyen", "Argileux", 65.00, "Pourriture", "USA", "Table, sans pepins"),
    (9, 2, "Tarocco", "moyen", "Volcanique", 50.00, "Alternaria", "Italie", "Jus rouge"),
    (10, 4, "Golden Delicious", "moyen", "Tous", 55.00, "Tavelure", "USA", "Table, polyvalent"),
    (11, 4, "Gala", "moyen", "Argileux", 50.00, "Oidium", "Nlle-Zelande", "Table rouge"),
    (12, 4, "Granny Smith", "moyen", "Franc", 60.00, "Feu bacterien", "Australie", "Verte acidee"),
    (13, 4, "Fuji", "moyen", "Sableux", 65.00, "Puceron", "Japon", "Tres sucree"),
    (14, 22, "Apache", "moyen", "Argileux", 80.00, "Rouille", "France", "Ble panifiable"),
    (15, 22, "Rustic", "moyen", "Tous", 75.00, "Fusariose", "France", "Ble tendre hiver"),
    (16, 23, "Miradoux", "moyen", "Calcaire", 55.00, "Septoriose", "France", "Ble dur semoule"),
    (17, 24, "Ariete", "elevetres_eleve", "Argileux", 85.00, "Pyricularia", "Italie", "Riz rond risotto"),
    (18, 24, "Japonica", "elevetres_eleve", "Argileux", 90.00, "Helmintho", "Japon", "Riz sushi"),
    (19, 25, "DK315", "moyen", "Tous", 120.00, "Pyrale", "France", "Mais grain"),
    (20, 26, "Esterel", "faible", "Calcaire", 65.00, "Rhyncho", "France", "Orge de brasserie"),
    (21, 33, "Kabuli", "faible", "Sableux", 25.00, "Ascochyta", "Inde", "Gros pois beige"),
    (22, 33, "Desi", "faible", "Argileux", 22.00, "Fusariose", "Inde", "Petit pois brun"),
    (23, 44, "Roma", "moyen", "Tous", 80.00, "Mildiou", "USA", "Allongee, sauce"),
    (24, 44, "Coeur de Boeuf", "moyen", "Argileux", 50.00, "Cladosporiose", "France", "Cotelee, grosse"),
    (25, 44, "Cerise", "moyen", "Tous", 90.00, "Lily", "France", "Petite ronde"),
    (26, 44, "Marmande", "moyen", "Argileux", 60.00, "Nematodes", "France", "Cotelee, pleine terre"),
    (27, 45, "Agata", "moyen", "Sableux", 45.00, "Mildiou", "Pays-Bas", "Primeur"),
    (28, 45, "Bintje", "moyen", "Tous", 50.00, "Jambe noire", "Pays-Bas", "Frite, polyvalente"),
    (29, 45, "Charlotte", "moyen", "Sableux", 35.00, "Gale", "France", "Chair ferme"),
    (30, 45, "Monalisa", "moyen", "Limoneux", 55.00, "PVY", "France", "Tous usages"),
    (31, 74, "Europe", "moyen", "Calcaire", 150.00, "Verticillium", "France", "Luzerne fourragere"),
    (32, 77, "Premium", "moyen", "Tous", 100.00, "Rouille", "France", "Ray-grass anglais"),
    (33, 87, "DP1212", "moyen", "Argileux", 35.00, "Helicoverpa", "USA", "Fibre longue"),
    (34, 97, "Chardonnay", "moyen", "Calcaire", 40.00, "Mildiou", "Bourgogne", "Vin blanc sec"),
    (35, 97, "Merlot", "moyen", "Argileux", 45.00, "Pourriture grise", "Bordeaux", "Vin rouge"),
    (36, 97, "Syrah", "faible", "Granitique", 35.00, "Oidium", "Cotes du Rhone", "Vin rouge epice"),
    (37, 116, "LG50575", "moyen", "Tous", 35.00, "Sclerotinia", "France", "Huile oleique"),
    (38, 117, "Alpaga", "moyen", "Argileux", 38.00, "Phoma", "France", "Colza hiver"),
    (39, 134, "Chine", "moyen", "Sableux", 15.00, "Rhizoctone", "Asie", "Gingembre frais"),
]

calendriers = [
    (1, "tempere", 2, 4, None, None, 10, 12, 365, "Mai-Juin (floraison)"),
    (2, "tempere", 3, 5, None, None, 11, 2, 365, "Avril-Mai"),
    (3, "mediterraneen", 3, 5, None, None, 10, 12, 365, "Avril"),
    (4, "tempere", 10, 12, None, None, 9, 10, 365, "Avril-Mai"),
    (10, "tempere", 10, 11, None, None, 8, 10, 180, "Avril"),
    (14, "tempere", 10, 11, None, None, 7, 8, 240, None),
    (15, "tempere", 10, 12, None, None, 7, 8, 250, None),
    (17, "tropical", 4, 6, None, None, 9, 11, 150, None),
    (19, "tempere", 4, 5, None, None, 10, 11, 160, None),
    (23, "mediterraneen", 2, 4, None, None, 6, 8, 90, None),
    (25, "tempere", 3, 5, None, None, 5, 10, 60, None),
    (27, "tempere", 4, 5, None, None, 7, 9, 120, None),
    (28, "tempere", 3, 5, None, None, 8, 10, 150, None),
    (31, "tempere", 4, 6, None, None, 5, 7, 100, None),
]

irrigations = [
    (1, "pluvial", 0.00, 0, 0, "Aucun besoin irrigation apres 2 ans", "Olivier adulte tolere secheresse"),
    (4, "pluvial", 0.00, 0, 0, "Jeune plantation: 10L/semaine", "Irrigation au goutte-a-goutte les 2 premieres annees"),
    (7, "goutte-a-goutte", 50.00, 7, 30, "Nouaison et grossissement", "Agrumes sensibles stress hydrique"),
    (10, "goutte-a-goutte", 30.00, 7, 60, "Grossissement fruits", "Eviter exces d'eau"),
    (23, "goutte-a-goutte", 25.00, 3, 20, "Fructification", "Irrigation reguliere evite eclatement"),
    (27, "aspersion", 15.00, 1, 10, "Tuberisation", "Stopper 15j avant recolte"),
    (17, "submersion", 200.00, 1, 360, "Tout le cycle", "Riziculture submergee"),
    (19, "goutte-a-goutte", 35.00, 5, 45, "Floraison", "Mais sensible stress hydrique floraison"),
    (14, "pluvial", 0.00, 0, 0, "Printemps", "Ble tendre surtout pluvial"),
]

maladies = [
    (1, "Mildiou", "champignon", "Bouillie bordelaise (cuivre), fongicides systemiques", "Maladie cryptogamique majeure, humide et chaud"),
    (2, "Oidium", "champignon", "Soufre, fongicides (triazoles)", "Blanc poudreux sur feuilles"),
    (3, "Rouille", "champignon", "Fongicides (triazoles, strobilurines)", "Pustules orange sur feuilles"),
    (4, "Fusariose", "champignon", "Rotation cultures, varietes resistantes, fongicides", "Fletrissement, pourriture des racines"),
    (5, "Verticillium", "champignon", "Solarisation, varietes resistantes, rotation", "Fletrissement vasculaire"),
    (6, "Mouche de l'olive", "insecte", "Piegeage massal, argile (kaolin), insecticides", "Larve dans l'olive"),
    (7, "Tavelure", "champignon", "Traitements cuivre, bouillie nantaise", "Crotes noires sur fruits et feuilles"),
    (8, "Puceron", "insecte", "Lutte biologique (coccinelle), huile de neem", "Colonies sur jeunes pousses"),
    (9, "Aleurode", "insecte", "Huile de neem, pieges jaunes, parasitoedes", "Mouche blanche, exsudat miellat"),
    (10, "Nematodes", "autre", "Rotation, varietes resistantes, solarisation", "Microvers racinaires"),
    (11, "Bacteriose", "bacterie", "Cuivre, arrachage plants contamines", "Taches huileuses sur feuilles"),
    (12, "Viroses diverses", "virus", "Arrachage plants, lutte pucerons vecteurs", "Mosaque, enroulement, nanisme"),
    (13, "Pourriture grise", "champignon", "Aeration, fongicides anti-botrytis", "Botrytis cinerea, moisissure grise"),
    (14, "Cladosporiose", "champignon", "Aeration, varietes resistantes", "Taches olives sur tomates"),
    (15, "Sclerotinia", "champignon", "Rotation, solarisation, Trichoderma", "Pourriture blanche"),
    (16, "Rhizoctone", "champignon", "Rotation, traitement sol", "Pourriture racinaire, fontes de semis"),
    (17, "Septoriose", "champignon", "Fongicides, varietes resistantes", "Taches brunes sur feuilles de ble"),
    (18, "Pyrale du mais", "insecte", "Lutte biologique (Trichogramma), Bt", "Chenille foreuse dans les tiges"),
    (19, "Chancre bacterien", "bacterie", "Cuivre, arrachage", "Chancre sur branches"),
    (20, "Feu bacterien", "bacterie", "Arrachage, quarantaine, cuivre", "Brlure des fleurs et rameaux"),
    (21, "Gale commune", "champignon", "Rotation, sol acide, varietes resistantes", "Crotes brunes sur pommes de terre"),
    (22, "Helicoverpa", "insecte", "Lutte integree, Bt, pieges", "Chenille du cotonnier"),
    (23, "Alternaria", "champignon", "Fongicides, varietes resistantes", "Taches brunes concentriques"),
    (24, "Mouche de la cerise", "insecte", "Pieges, filets, argile", "Larve dans les cerises"),
    (25, "Cochenille", "insecte", "Huile blanche, lutte biologique", "Carapace cireuse, miellat"),
]

plantes_maladies = [
    (1, 5), (1, 6), (2, 23), (2, 8), (3, 23), (3, 8),
    (4, 7), (4, 20), (4, 8), (5, 7), (5, 20),
    (6, 1), (6, 8), (7, 1), (7, 8), (8, 24),
    (10, 1), (10, 8),
    (22, 17), (22, 3), (22, 4), (23, 17),
    (24, 1), (24, 2), (24, 4),
    (25, 3), (25, 18), (25, 4), (27, 3), (27, 4),
    (33, 4), (33, 23), (34, 4), (34, 23),
    (44, 1), (44, 14), (44, 8), (44, 9), (44, 10),
    (45, 1), (45, 21), (45, 4), (45, 8),
    (74, 5), (74, 1),
    (87, 22), (87, 8), (97, 1), (97, 2), (97, 13),
    (116, 15), (117, 15), (117, 4),
    (134, 16), (135, 16),
]

guides = [
    (1, "taille", "Taille de formation Olivier", "Formation en gobelet les 3 premieres annees. Supprimer bois mort et gourmands.", "Hiver"),
    (22, "semis", "Semis de ble d'hiver", "Semis octobre-novembre, densite 250-300 grains/m2, profondeur 2-3cm", "Automne"),
    (44, "semis", "Semis tomate sous serre", "Semis mars-avril en alveoles, repiquage stade 2-4 feuilles", "Printemps"),
    (44, "plantation", "Plantation tomate plein champ", "Ecarterement 0.8m x 0.4m, tuteurage obligatoire", "Mai"),
    (45, "plantation", "Plantation pomme de terre", "Buttes 10-15cm, ecartement 0.75m, profondeur 8-10cm", "Mars-Mai"),
    (74, "semis", "Implantation luzerne", "Semis printemps, profondeur 1cm, densite 15-20 kg/ha", "Printemps"),
    (97, "taille", "Taille vigne", "Taille guyot simple: 1 courson a 2 yeux + 1 baguette a 8 yeux", "Fevrier"),
]

# =========================================================
# EXECUTION
# =========================================================

def seed():
    print("Seeding plant database...")

    # Categories
    cur.executemany("INSERT IGNORE INTO categories (id, nom, description) VALUES (%s, %s, %s)", categories)
    print(f"  categories: {cur.rowcount} rows")

    # Familles botaniques
    cur.executemany("INSERT IGNORE INTO familles_botaniques (id, nom, description) VALUES (%s, %s, %s)", familles)
    print(f"  familles: {cur.rowcount} rows")

    # Plantes
    cur.executemany("""INSERT IGNORE INTO plantes (id, nom_commun, nom_scientifique, id_categorie, id_famille, cycle_vie, description)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""", plantes)
    print(f"  plantes: {cur.rowcount} rows")

    # Varietes
    cur.executemany("""INSERT IGNORE INTO varietes (id, id_plante, nom, besoin_eau, type_sol_ideal, rendement_estime, resistance_maladies, origine, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", varietes)
    print(f"  varietes: {cur.rowcount} rows")

    # Calendrier
    cur.executemany("""INSERT IGNORE INTO calendrier_culture (id_variete, zone_climatique, mois_semis_debut, mois_semis_fin, mois_plantation_debut, mois_plantation_fin, mois_recolte_debut, mois_recolte_fin, duree_cycle_jours, periode_floraison)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [(c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9]) for c in calendriers])
    print(f"  calendrier: {cur.rowcount} rows")

    # Irrigation
    cur.executemany("""INSERT IGNORE INTO irrigation (id_variete, methode, frequence_mm_semaine, frequence_jours, duree_minutes, stade_critique, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) for i in irrigations])
    print(f"  irrigation: {cur.rowcount} rows")

    # Maladies
    cur.executemany("""INSERT IGNORE INTO maladies (id, nom, type_agent, type_traitement, description)
                       VALUES (%s, %s, %s, %s, %s)""", maladies)
    print(f"  maladies: {cur.rowcount} rows")

    # Plantes-Maladies
    # Check if table has sensibilite column
    has_sens = False
    cur.execute("SHOW COLUMNS FROM plantes_maladies LIKE 'sensibilite'")
    if cur.fetchone():
        has_sens = True

    if has_sens:
        cur.executemany("INSERT IGNORE INTO plantes_maladies (id_plante, id_maladie, sensibilite) VALUES (%s, %s, 'moyenne')", plantes_maladies)
    else:
        cur.executemany("INSERT IGNORE INTO plantes_maladies (id_plante, id_maladie) VALUES (%s, %s)", plantes_maladies)
    print(f"  plantes_maladies: {cur.rowcount} rows")

    # Guides
    cur.executemany("""INSERT IGNORE INTO guides_culture (id_plante, type_guide, titre, contenu, saison_recommandee)
                       VALUES (%s, %s, %s, %s, %s)""", guides)
    print(f"  guides: {cur.rowcount} rows")

    conn.commit()
    print("\nDone! Database seeded successfully.")

def count_tables():
    for t in ["categories", "familles_botaniques", "plantes", "varietes",
              "calendrier_culture", "irrigation", "maladies",
              "plantes_maladies", "analyses_sol", "microbiologie_sol", "guides_culture"]:
        cur.execute(f"SELECT COUNT(*) as c FROM {t}")
        r = cur.fetchone()
        print(f"  {t}: {r['c']} rows")


if __name__ == "__main__":
    seed()
    print()
    count_tables()
    conn.close()
