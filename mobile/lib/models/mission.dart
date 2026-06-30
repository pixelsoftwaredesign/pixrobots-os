// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Mission {
  final String id;
  final String robotId;
  final String robotName;
  final String zone;
  final List<String> actions;
  final String status;
  final String createdAt;
  final String? completedAt;
  final String? cropSpecies;
  final String? cropStage;
  final Map<String, dynamic>? results;

  Mission({
    required this.id,
    required this.robotId,
    required this.robotName,
    required this.zone,
    required this.actions,
    required this.status,
    required this.createdAt,
    this.completedAt,
    this.cropSpecies,
    this.cropStage,
    this.results,
  });

  factory Mission.fromJson(Map<String, dynamic> json) {
    return Mission(
      id: json['id'] ?? '',
      robotId: json['robot_id'] ?? '',
      robotName: json['robot_name'] ?? '',
      zone: json['zone'] ?? '',
      actions: List<String>.from(json['actions'] ?? []),
      status: json['status'] ?? 'pending',
      createdAt: json['created_at'] ?? '',
      completedAt: json['completed_at'],
      cropSpecies: json['crop_species'],
      cropStage: json['crop_stage'],
      results: json['results'] as Map<String, dynamic>?,
    );
  }
}
