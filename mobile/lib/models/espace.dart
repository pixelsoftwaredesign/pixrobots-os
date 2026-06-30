// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
class Espace {
  final int id;
  final String nom;
  final String? localisation;
  final double? superficieTotale;
  final String? description;
  final bool active;

  Espace({
    required this.id,
    required this.nom,
    this.localisation,
    this.superficieTotale,
    this.description,
    required this.active,
  });

  factory Espace.fromJson(Map<String, dynamic> json) {
    return Espace(
      id: json['id'],
      nom: json['nom'],
      localisation: json['localisation'],
      superficieTotale: (json['superficieTotale'] as num?)?.toDouble(),
      description: json['description'],
      active: json['active'] ?? true,
    );
  }
}
