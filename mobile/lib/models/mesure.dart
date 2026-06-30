// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Mesure {
  final String id;
  final int zoneId;
  final String zoneNom;
  final double humidite;
  final double? temperature;
  final String timestamp;

  Mesure({
    required this.id,
    required this.zoneId,
    required this.zoneNom,
    required this.humidite,
    this.temperature,
    required this.timestamp,
  });

  factory Mesure.fromJson(Map<String, dynamic> json) {
    return Mesure(
      id: json['id'],
      zoneId: json['zoneId'],
      zoneNom: json['zoneNom'],
      humidite: (json['humidite'] as num).toDouble(),
      temperature: (json['temperature'] as num?)?.toDouble(),
      timestamp: json['timestamp'],
    );
  }
}
