// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/robot.dart';
import '../models/mission.dart';
import '../services/api_service.dart';
import '../services/mqtt_service.dart';

class RobotsProvider extends ChangeNotifier {
  final ApiService _api;
  final MqttService _mqtt;
  List<Robot> _robots = [];
  List<Mission> _missions = [];
  bool _loading = false;
  String? _error;

  List<Robot> get robots => _robots;
  List<Mission> get missions => _missions;
  bool get loading => _loading;
  String? get error => _error;

  RobotsProvider(this._api, this._mqtt) {
    _mqtt.onMessage((topic, payload) {
      if (topic.startsWith('robots/') && topic.endsWith('/status')) {
        final robotId = topic.split('/')[1];
        final idx = _robots.indexWhere((r) => r.id == robotId);
        final robot = Robot(
          id: robotId,
          name: payload['name'] ?? robotId,
          role: payload['role'] ?? '',
          status: payload['status'] ?? 'unknown',
          battery: (payload['battery'] as num?)?.toDouble() ?? 0,
          posX: (payload['pos_x'] as num?)?.toDouble(),
          posY: (payload['pos_y'] as num?)?.toDouble(),
          currentMission: payload['current_mission'],
          lastHeartbeat: DateTime.now().toIso8601String(),
          temperature: (payload['temperature'] as num?)?.toDouble(),
          online: true,
        );
        if (idx >= 0) {
          _robots[idx] = robot;
        } else {
          _robots.add(robot);
        }
        notifyListeners();
      }
    });
  }

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _robots = await _api.getRobots();
      _missions = await _api.getMissions();
    } catch (e) {
      _error = e.toString();
    }
    _loading = false;
    notifyListeners();
  }

  Future<Mission> sendMission(String robotId, String zone, List<String> actions, {String? cropSpecies, String? cropStage}) async {
    final mission = await _api.creerMission({
      'robot_id': robotId,
      'zone': zone,
      'actions': actions,
      'crop_species': cropSpecies,
      'crop_stage': cropStage,
    });
    _missions.insert(0, mission);
    notifyListeners();
    return mission;
  }

  Robot? byId(String id) {
    try {
      return _robots.firstWhere((r) => r.id == id);
    } catch (_) {
      return null;
    }
  }
}
