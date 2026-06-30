// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import '../providers/auth_provider.dart';
import '../models/espace.dart';
import '../models/zone.dart';

class ZonesScreen extends StatefulWidget {
  const ZonesScreen({super.key});
  @override
  State<ZonesScreen> createState() => _ZonesScreenState();
}

class _ZonesScreenState extends State<ZonesScreen> {
  late Future<List<Espace>> _espaces;
  final _nomCtrl = TextEditingController();
  final _locCtrl = TextEditingController();
  final _supCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _espaces = context.read<AuthProvider>().api.getEspaces();
  }

  Color _humidityColor(double h) {
    if (h < 30) return Colors.red;
    if (h < 60) return Colors.orange;
    return Colors.green;
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _espaces = context.read<AuthProvider>().api.getEspaces()),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(children: [
            Text('Zones & Espaces', style: Theme.of(context).textTheme.titleLarge),
            const Spacer(),
            IconButton(icon: const Icon(Icons.add), onPressed: () => _showCreateEspaceDialog(context)),
          ]),
          const SizedBox(height: 8),
          FutureBuilder<List<Espace>>(
            future: _espaces,
            builder: (context, snapshot) {
              if (snapshot.hasError) return Center(child: Text('Erreur: ${snapshot.error}'));
              if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
              final espaces = snapshot.data!;
              if (espaces.isEmpty) return const Center(child: Text('Aucun espace. CrÃ©ez-en un.'));
              return Column(
                children: espaces.map((e) => _buildEspaceCard(e)).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildEspaceCard(Espace espace) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: ExpansionTile(
        title: Text(espace.nom, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(espace.localisation ?? ''),
        leading: const Icon(Icons.agriculture),
        children: [
          FutureBuilder<List<Zone>>(
            future: context.read<AuthProvider>().api.getZonesByEspace(espace.id),
            builder: (context, snapshot) {
              if (!snapshot.hasData || snapshot.data!.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Aucune zone'),
                );
              }
              return Column(
                children: snapshot.data!.map((z) => _buildZoneCard(z)).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildZoneCard(Zone zone) {
    final h = zone.derniereHumidite ?? 0;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: Colors.grey[100], borderRadius: BorderRadius.circular(8)),
      child: Row(
        children: [
          SizedBox(
            height: 60, width: 60,
            child: PieChart(PieChartData(sections: [
              PieChartSectionData(value: h, color: _humidityColor(h), radius: 20, title: '${h.toStringAsFixed(0)}%'),
              PieChartSectionData(value: 100 - h, color: Colors.grey[300], radius: 20),
            ])),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(zone.nom, style: const TextStyle(fontWeight: FontWeight.bold)),
                if (zone.culture != null) Text(zone.culture!),
                Text('Seuil: ${zone.seuilHumidite?.toStringAsFixed(0) ?? "N/A"}%'),
              ],
            ),
          ),
          Icon(zone.active ? Icons.check_circle : Icons.cancel, color: zone.active ? Colors.green : Colors.red),
        ],
      ),
    );
  }

  void _showCreateEspaceDialog(BuildContext context) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Nouvel Espace'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(controller: _nomCtrl, decoration: const InputDecoration(labelText: 'Nom')),
          TextField(controller: _locCtrl, decoration: const InputDecoration(labelText: 'Localisation')),
          TextField(controller: _supCtrl, decoration: const InputDecoration(labelText: 'Superficie (ha)'), keyboardType: TextInputType.number),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
        ElevatedButton(onPressed: () async {
          await context.read<AuthProvider>().api.creerEspace({
            'nom': _nomCtrl.text,
            'localisation': _locCtrl.text,
            'superficieTotale': double.tryParse(_supCtrl.text),
            'active': true,
          });
          if (ctx.mounted) Navigator.pop(ctx);
          setState(() => _espaces = context.read<AuthProvider>().api.getEspaces());
        }, child: const Text('CrÃ©er')),
      ],
    ));
  }

  @override
  void dispose() {
    _nomCtrl.dispose();
    _locCtrl.dispose();
    _supCtrl.dispose();
    super.dispose();
  }
}
