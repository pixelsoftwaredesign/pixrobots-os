// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/espace.dart';
import '../models/zone.dart';
import '../models/mesure.dart';
import '../models/sensor.dart';
import '../models/robot.dart';
import '../models/mission.dart';
import '../models/alert.dart';

class ApiService {
  String baseUrl;

  ApiService({this.baseUrl = 'http://localhost:8080/api'});

  Future<void> setBaseUrl(String url) {
    baseUrl = url;
    return Future.value();
  }

  Future<Map<String, String>> _headers() async {
    return {'Content-Type': 'application/json'};
  }

  Future<List<Espace>> getEspaces() async {
    final response = await http.get(Uri.parse('$baseUrl/espaces'), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Espace.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement espaces: ${response.statusCode}');
  }

  Future<Espace> creerEspace(Map<String, dynamic> data) async {
    final response = await http.post(Uri.parse('$baseUrl/espaces'), headers: await _headers(), body: json.encode(data));
    if (response.statusCode == 200) {
      return Espace.fromJson(json.decode(response.body));
    }
    throw Exception('Erreur crÃ©ation espace: ${response.statusCode}');
  }

  Future<List<Zone>> getZones() async {
    final response = await http.get(Uri.parse('$baseUrl/zones'), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Zone.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement zones: ${response.statusCode}');
  }

  Future<List<Zone>> getZonesByEspace(int espaceId) async {
    final response = await http.get(Uri.parse('$baseUrl/espaces/$espaceId/zones'), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Zone.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement zones');
  }

  Future<Zone> creerZone(int espaceId, Map<String, dynamic> data) async {
    final response = await http.post(Uri.parse('$baseUrl/espaces/$espaceId/zones'), headers: await _headers(), body: json.encode(data));
    if (response.statusCode == 200) {
      return Zone.fromJson(json.decode(response.body));
    }
    throw Exception('Erreur crÃ©ation zone');
  }

  Future<List<Mesure>> getMesures(int zoneId) async {
    final response = await http.get(Uri.parse('$baseUrl/mesures/$zoneId'), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Mesure.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement mesures');
  }

  Future<void> commanderIrrigation(int zoneId, bool ouvrir) async {
    final response = await http.post(Uri.parse('$baseUrl/irrigation/commande'), headers: await _headers(),
        body: json.encode({'zoneId': zoneId, 'ouvrir': ouvrir}));
    if (response.statusCode != 200) {
      throw Exception('Erreur commande irrigation');
    }
  }

  Future<Map<String, dynamic>> getPixStatus() async {
    final response = await http.get(Uri.parse('$baseUrl/pixos/status'), headers: await _headers());
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Erreur status Pixel OS');
  }

  Future<List<Sensor>> getSensors({String? zone}) async {
    final uri = zone != null ? '$baseUrl/sensors?zone=$zone' : '$baseUrl/sensors';
    final response = await http.get(Uri.parse(uri), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Sensor.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement capteurs');
  }

  Future<List<Robot>> getRobots() async {
    final response = await http.get(Uri.parse('$baseUrl/robots'), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Robot.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement robots');
  }

  Future<List<Mission>> getMissions({String? robotId}) async {
    final uri = robotId != null ? '$baseUrl/missions?robot_id=$robotId' : '$baseUrl/missions';
    final response = await http.get(Uri.parse(uri), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Mission.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement missions');
  }

  Future<Mission> creerMission(Map<String, dynamic> data) async {
    final response = await http.post(Uri.parse('$baseUrl/missions'), headers: await _headers(), body: json.encode(data));
    if (response.statusCode == 200) {
      return Mission.fromJson(json.decode(response.body));
    }
    throw Exception('Erreur crÃ©ation mission');
  }

  Future<List<Alert>> getAlerts({bool? unacknowledged}) async {
    final uri = unacknowledged == true ? '$baseUrl/alerts?unacknowledged=true' : '$baseUrl/alerts';
    final response = await http.get(Uri.parse(uri), headers: await _headers());
    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Alert.fromJson(e)).toList();
    }
    throw Exception('Erreur chargement alertes');
  }

  Future<void> acknowledgeAlert(String alertId) async {
    final response = await http.post(Uri.parse('$baseUrl/alerts/$alertId/acknowledge'), headers: await _headers());
    if (response.statusCode != 200) {
      throw Exception('Erreur acquittement alerte');
    }
  }
}
