// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Sensor {
  final String id;
  final String nodeId;
  final String type;
  final double value;
  final String unit;
  final String zone;
  final double battery;
  final String lastSeen;
  final bool online;

  Sensor({
    required this.id,
    required this.nodeId,
    required this.type,
    required this.value,
    required this.unit,
    required this.zone,
    required this.battery,
    required this.lastSeen,
    required this.online,
  });

  factory Sensor.fromJson(Map<String, dynamic> json) {
    return Sensor(
      id: json['id'] ?? '',
      nodeId: json['node_id'] ?? '',
      type: json['type'] ?? '',
      value: (json['value'] as num?)?.toDouble() ?? 0,
      unit: json['unit'] ?? '',
      zone: json['zone'] ?? '',
      battery: (json['battery'] as num?)?.toDouble() ?? 100,
      lastSeen: json['last_seen'] ?? '',
      online: json['online'] ?? false,
    );
  }
}
