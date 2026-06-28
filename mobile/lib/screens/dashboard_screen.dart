import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/espace.dart';
import '../models/zone.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _api = ApiService();
  late Future<List<Espace>> _espaces;
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    _espaces = _api.getEspaces();
  }

  Color _couleurHumidite(double h) {
    if (h < 30) return Colors.red;
    if (h < 60) return Colors.orange;
    return Colors.green;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AgriCol')),
      body: _selectedIndex == 0 ? _buildDashboard() : _buildGestion(),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        destinations: const [
          NavigationDestination(Icons.dashboard, 'Dashboard'),
          NavigationDestination(Icons.settings, 'Gestion'),
        ],
      ),
    );
  }

  Widget _buildDashboard() {
    return FutureBuilder<List<Espace>>(
      future: _espaces,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(child: Text('Erreur: ${snapshot.error}'));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final espaces = snapshot.data!;
        if (espaces.isEmpty) {
          return const Center(child: Text('Aucun espace. Créez-en un dans Gestion.'));
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: espaces.map((e) => _buildEspaceCard(e)).toList(),
        );
      },
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
            future: _api.getZonesByEspace(espace.id),
            builder: (context, snapshot) {
              if (!snapshot.hasData || snapshot.data!.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text('Aucune zone dans cet espace'),
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
      decoration: BoxDecoration(
        color: Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          SizedBox(
            height: 60,
            width: 60,
            child: PieChart(
              PieChartData(
                sections: [
                  PieChartSectionData(
                    value: h, color: _couleurHumidite(h),
                    radius: 20, title: '${h.toStringAsFixed(0)}%'),
                  PieChartSectionData(
                    value: 100 - h, color: Colors.grey[300], radius: 20),
                ],
              ),
            ),
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
          Icon(
            zone.active ? Icons.check_circle : Icons.cancel,
            color: zone.active ? Colors.green : Colors.red,
          ),
        ],
      ),
    );
  }

  Widget _buildGestion() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Créer un Espace',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        _buildCreerEspaceForm(),
        const SizedBox(height: 24),
        const Text('Créer une Zone',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        _buildCreerZoneForm(),
      ],
    );
  }

  Widget _buildCreerEspaceForm() {
    final nomCtrl = TextEditingController();
    final locCtrl = TextEditingController();
    final supCtrl = TextEditingController();
    final result = ValueNotifier<String>('');

    return ValueListenableBuilder(
      valueListenable: result,
      builder: (context, msg, _) => Column(
        children: [
          TextField(controller: nomCtrl, decoration: const InputDecoration(labelText: 'Nom')),
          TextField(controller: locCtrl, decoration: const InputDecoration(labelText: 'Localisation')),
          TextField(controller: supCtrl, decoration: const InputDecoration(labelText: 'Superficie (ha)'), keyboardType: TextInputType.number),
          ElevatedButton(
            onPressed: () async {
              try {
                await _api.creerEspace({
                  'nom': nomCtrl.text,
                  'localisation': locCtrl.text,
                  'superficieTotale': double.tryParse(supCtrl.text),
                  'active': true,
                });
                result.value = 'Espace créé !';
                _espaces = _api.getEspaces();
                setState(() {});
              } catch (e) {
                result.value = 'Erreur: $e';
              }
            },
            child: const Text('Créer'),
          ),
          Text(msg),
        ],
      ),
    );
  }

  Widget _buildCreerZoneForm() {
    final nomCtrl = TextEditingController();
    final supCtrl = TextEditingController();
    final cultureCtrl = TextEditingController();
    final seuilCtrl = TextEditingController();
    final espaceIdCtrl = TextEditingController();
    final result = ValueNotifier<String>('');

    return ValueListenableBuilder(
      valueListenable: result,
      builder: (context, msg, _) => Column(
        children: [
          TextField(controller: nomCtrl, decoration: const InputDecoration(labelText: 'Nom')),
          TextField(controller: supCtrl, decoration: const InputDecoration(labelText: 'Superficie'), keyboardType: TextInputType.number),
          TextField(controller: cultureCtrl, decoration: const InputDecoration(labelText: 'Culture')),
          TextField(controller: seuilCtrl, decoration: const InputDecoration(labelText: 'Seuil humidité (%)'), keyboardType: TextInputType.number),
          TextField(controller: espaceIdCtrl, decoration: const InputDecoration(labelText: 'ID Espace'), keyboardType: TextInputType.number),
          ElevatedButton(
            onPressed: () async {
              try {
                await _api.creerZone(int.parse(espaceIdCtrl.text), {
                  'nom': nomCtrl.text,
                  'superficie': double.parse(supCtrl.text),
                  'culture': cultureCtrl.text,
                  'seuilHumidite': double.tryParse(seuilCtrl.text),
                  'active': true,
                });
                result.value = 'Zone créée !';
              } catch (e) {
                result.value = 'Erreur: $e';
              }
            },
            child: const Text('Créer'),
          ),
          Text(msg),
        ],
      ),
    );
  }
}
