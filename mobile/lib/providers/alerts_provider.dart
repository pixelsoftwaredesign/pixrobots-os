// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/foundation.dart';
import '../models/alert.dart';
import '../services/api_service.dart';
import '../services/mqtt_service.dart';

class AlertsProvider extends ChangeNotifier {
  final ApiService _api;
  final MqttService _mqtt;
  List<Alert> _alerts = [];
  int _unacknowledgedCount = 0;
  bool _loading = false;

  List<Alert> get alerts => _alerts;
  int get unacknowledgedCount => _unacknowledgedCount;
  bool get loading => _loading;

  AlertsProvider(this._api, this._mqtt) {
    _mqtt.onMessage((topic, payload) {
      if (topic.startsWith('alerts/')) {
        final alert = Alert(
          id: payload['id'] ?? '${DateTime.now().millisecondsSinceEpoch}',
          type: payload['type'] ?? 'unknown',
          severity: payload['severity'] ?? 'info',
          title: payload['title'] ?? 'Alerte',
          message: payload['message'] ?? '',
          zone: payload['zone'] ?? '',
          timestamp: payload['timestamp'] ?? DateTime.now().toIso8601String(),
          acknowledged: false,
        );
        _alerts.insert(0, alert);
        _unacknowledgedCount++;
        notifyListeners();
      }
    });
  }

  Future<void> load() async {
    _loading = true;
    notifyListeners();
    try {
      _alerts = await _api.getAlerts();
      _unacknowledgedCount = _alerts.where((a) => !a.acknowledged).length;
    } catch (_) {}
    _loading = false;
    notifyListeners();
  }

  Future<void> acknowledge(String alertId) async {
    try {
      await _api.acknowledgeAlert(alertId);
      final idx = _alerts.indexWhere((a) => a.id == alertId);
      if (idx >= 0) {
        _alerts[idx] = Alert(
          id: _alerts[idx].id,
          type: _alerts[idx].type,
          severity: _alerts[idx].severity,
          title: _alerts[idx].title,
          message: _alerts[idx].message,
          zone: _alerts[idx].zone,
          timestamp: _alerts[idx].timestamp,
          acknowledged: true,
        );
        _unacknowledgedCount = _alerts.where((a) => !a.acknowledged).length;
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> acknowledgeAll() async {
    for (final alert in _alerts.where((a) => !a.acknowledged)) {
      await acknowledge(alert.id);
    }
  }
}
