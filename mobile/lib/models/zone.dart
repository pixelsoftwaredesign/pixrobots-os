class Zone {
  final int id;
  final String nom;
  final double superficie;
  final String? culture;
  final double? seuilHumidite;
  final int? espaceId;
  final String? espaceNom;
  final bool active;
  final double? derniereHumidite;
  final String? derniereMesure;

  Zone({
    required this.id,
    required this.nom,
    required this.superficie,
    this.culture,
    this.seuilHumidite,
    this.espaceId,
    this.espaceNom,
    required this.active,
    this.derniereHumidite,
    this.derniereMesure,
  });

  factory Zone.fromJson(Map<String, dynamic> json) {
    return Zone(
      id: json['id'],
      nom: json['nom'],
      superficie: (json['superficie'] as num).toDouble(),
      culture: json['culture'],
      seuilHumidite: (json['seuilHumidite'] as num?)?.toDouble(),
      espaceId: json['espaceId'],
      espaceNom: json['espaceNom'],
      active: json['active'] ?? true,
      derniereHumidite: (json['derniereHumidite'] as num?)?.toDouble(),
      derniereMesure: json['derniereMesure'],
    );
  }
}
