// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Robot {
  final String id;
  final String name;
  final String role;
  final String status;
  final double battery;
  final double? posX;
  final double? posY;
  final String? currentMission;
  final String lastHeartbeat;
  final double? temperature;
  final bool online;

  Robot({
    required this.id,
    required this.name,
    required this.role,
    required this.status,
    required this.battery,
    this.posX,
    this.posY,
    this.currentMission,
    required this.lastHeartbeat,
    this.temperature,
    required this.online,
  });

  factory Robot.fromJson(Map<String, dynamic> json) {
    return Robot(
      id: json['id'] ?? '',
      name: json['name'] ?? '',
      role: json['role'] ?? '',
      status: json['status'] ?? 'unknown',
      battery: (json['battery'] as num?)?.toDouble() ?? 0,
      posX: (json['pos_x'] as num?)?.toDouble(),
      posY: (json['pos_y'] as num?)?.toDouble(),
      currentMission: json['current_mission'],
      lastHeartbeat: json['last_heartbeat'] ?? '',
      temperature: (json['temperature'] as num?)?.toDouble(),
      online: json['online'] ?? false,
    );
  }
}
