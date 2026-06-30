// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Alert {
  final String id;
  final String type;
  final String severity;
  final String title;
  final String message;
  final String zone;
  final String timestamp;
  final bool acknowledged;

  Alert({
    required this.id,
    required this.type,
    required this.severity,
    required this.title,
    required this.message,
    required this.zone,
    required this.timestamp,
    required this.acknowledged,
  });

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] ?? '',
      type: json['type'] ?? '',
      severity: json['severity'] ?? 'info',
      title: json['title'] ?? '',
      message: json['message'] ?? '',
      zone: json['zone'] ?? '',
      timestamp: json['timestamp'] ?? '',
      acknowledged: json['acknowledged'] ?? false,
    );
  }
}
