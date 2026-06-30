// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/sensor.dart';
import '../services/api_service.dart';
import '../services/mqtt_service.dart';

class SensorsProvider extends ChangeNotifier {
  final ApiService _api;
  final MqttService _mqtt;
  List<Sensor> _sensors = [];
  bool _loading = false;
  String? _error;
  StreamSubscription? _mqttSub;

  List<Sensor> get sensors => _sensors;
  bool get loading => _loading;
  String? get error => _error;

  SensorsProvider(this._api, this._mqtt) {
    _mqttSub = null;
  }

  void initMqtt() {
    _mqtt.onMessage((topic, payload) {
      if (topic.startsWith('sensors/')) {
        final parts = topic.split('/');
        if (parts.length >= 3) {
          final zone = parts[1];
          final type = parts[2];
          final idx = _sensors.indexWhere((s) => s.zone == zone && s.type == type);
          final sensor = Sensor(
            id: payload['record_id'] ?? '${DateTime.now().millisecondsSinceEpoch}',
            nodeId: payload['node_id'] ?? '',
            type: type,
            value: (payload['sensor']?['value'] as num?)?.toDouble() ?? 0,
            unit: payload['sensor']?['unit'] ?? '',
            zone: zone,
            battery: (payload['battery'] as num?)?.toDouble() ?? 100,
            lastSeen: DateTime.now().toIso8601String(),
            online: true,
          );
          if (idx >= 0) {
            _sensors[idx] = sensor;
          } else {
            _sensors.add(sensor);
          }
          notifyListeners();
        }
      }
    });
  }

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _sensors = await _api.getSensors();
    } catch (e) {
      _error = e.toString();
    }
    _loading = false;
    notifyListeners();
  }

  List<Sensor> byZone(String zone) => _sensors.where((s) => s.zone == zone).toList();

  @override
  void dispose() {
    _mqttSub?.cancel();
    super.dispose();
  }
}
