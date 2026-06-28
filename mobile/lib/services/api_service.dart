import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/espace.dart';
import '../models/zone.dart';
import '../models/mesure.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8080/api';

  Future<List<Espace>> getEspaces() async {
    final response = await http.get(Uri.parse('$baseUrl/espaces'));
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Espace.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement espaces');
  }

  Future<Espace> creerEspace(Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/espaces'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(data),
    );
    if (response.statusCode == 200) {
      return Espace.fromJson(json.decode(response.body));
    }
    throw Exception('Erreur création espace');
  }

  Future<List<Zone>> getZones() async {
    final response = await http.get(Uri.parse('$baseUrl/zones'));
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Zone.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement zones');
  }

  Future<List<Zone>> getZonesByEspace(int espaceId) async {
    final response = await http.get(Uri.parse('$baseUrl/espaces/$espaceId/zones'));
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Zone.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement zones');
  }

  Future<Zone> creerZone(int espaceId, Map<String, dynamic> data) async {
    final response = await http.post(
      Uri.parse('$baseUrl/espaces/$espaceId/zones'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(data),
    );
    if (response.statusCode == 200) {
      return Zone.fromJson(json.decode(response.body));
    }
    throw Exception('Erreur création zone');
  }

  Future<List<Mesure>> getMesures(int zoneId) async {
    final response = await http.get(Uri.parse('$baseUrl/mesures/$zoneId'));
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Mesure.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement mesures');
  }

  Future<void> commanderIrrigation(int zoneId, bool ouvrir) async {
    final response = await http.post(
      Uri.parse('$baseUrl/irrigation/commande'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({'zoneId': zoneId, 'ouvrir': ouvrir}),
    );
    if (response.statusCode != 200) {
      throw Exception('Erreur commande irrigation');
    }
  }
}
