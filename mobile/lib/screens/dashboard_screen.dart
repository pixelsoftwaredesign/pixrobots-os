// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/sensors_provider.dart';
import '../providers/robots_provider.dart';
import '../providers/alerts_provider.dart';
import '../widgets/sensor_card.dart';
import '../widgets/robot_card.dart';
import 'zones_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadData());
  }

  Future<void> _loadData() async {
    final api = context.read<AuthProvider>().api;
    if (!context.mounted) return;
    try {
      final status = await api.getPixStatus();
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Pixel OS ${status['version'] ?? ''} â€” ${status['uptime'] ?? ''}'), duration: const Duration(seconds: 2)),
        );
      }
    } catch (_) {}
    if (context.mounted) {
      context.read<SensorsProvider>().load();
      context.read<RobotsProvider>().load();
      context.read<AlertsProvider>().load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final alerts = context.watch<AlertsProvider>();
    final unread = alerts.unacknowledgedCount;
    return Scaffold(
      appBar: AppBar(
        title: const Text('AgriculApp'),
        actions: [
          if (unread > 0)
            Stack(
              children: [
                IconButton(icon: const Icon(Icons.notifications), onPressed: () => setState(() => _selectedIndex = 4)),
                Positioned(right: 6, top: 6, child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                  child: Text('$unread', style: const TextStyle(color: Colors.white, fontSize: 10)),
                )),
              ],
            )
          else
            IconButton(icon: const Icon(Icons.notifications_none), onPressed: () => setState(() => _selectedIndex = 4)),
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'logout') context.read<AuthProvider>().logout();
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'logout', child: Row(children: [Icon(Icons.logout), SizedBox(width: 8), Text('DÃ©connexion')])),
            ],
          ),
        ],
      ),
      body: _buildBody(),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard), label: 'Vue d\'ensemble'),
          NavigationDestination(icon: Icon(Icons.sensors), label: 'Capteurs'),
          NavigationDestination(icon: Icon(Icons.smart_toy), label: 'Robots'),
          NavigationDestination(icon: Icon(Icons.assignment), label: 'Zones'),
          NavigationDestination(icon: Icon(Icons.notifications), label: 'Alertes'),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_selectedIndex) {
      case 0: return _buildOverview();
      case 1: return const SensorsScreen();
      case 2: return const RobotsScreen();
      case 3: return const ZonesScreen();
      case 4: return const AlertsScreen();
      default: return _buildOverview();
    }
  }

  Widget _buildOverview() {
    final sensors = context.watch<SensorsProvider>();
    final robots = context.watch<RobotsProvider>();
    final alerts = context.watch<AlertsProvider>();
    return RefreshIndicator(
      onRefresh: () async => _loadData(),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Ferme connectÃ©e', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          Row(
            children: [
              _StatCard(icon: Icons.sensors, label: 'Capteurs', value: '${sensors.sensors.length}', color: Colors.blue),
              const SizedBox(width: 12),
              _StatCard(icon: Icons.smart_toy, label: 'Robots', value: '${robots.robots.length}', color: Colors.green),
              const SizedBox(width: 12),
              _StatCard(icon: Icons.warning, label: 'Alertes', value: '${alerts.unacknowledgedCount}', color: alerts.unacknowledgedCount > 0 ? Colors.red : Colors.grey),
            ],
          ),
          const SizedBox(height: 24),
          Text('Capteurs rÃ©cents', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...sensors.sensors.take(4).map((s) => SensorCard(sensor: s)),
          const SizedBox(height: 24),
          Text('Robots', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...robots.robots.map((r) => RobotCard(robot: r)),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color color;
  const _StatCard({required this.icon, required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Icon(icon, color: color, size: 32),
              const SizedBox(height: 8),
              Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
              Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
            ],
          ),
        ),
      ),
    );
  }
}

class SensorsScreen extends StatelessWidget {
  const SensorsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final sensors = context.watch<SensorsProvider>();
    if (sensors.loading) return const Center(child: CircularProgressIndicator());
    if (sensors.error != null) return Center(child: Text('Erreur: ${sensors.error}'));
    if (sensors.sensors.isEmpty) return const Center(child: Text('Aucun capteur'));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: sensors.sensors.map((s) => SensorCard(sensor: s)).toList(),
    );
  }
}

class RobotsScreen extends StatelessWidget {
  const RobotsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final robots = context.watch<RobotsProvider>();
    if (robots.loading) return const Center(child: CircularProgressIndicator());
    if (robots.robots.isEmpty) return const Center(child: Text('Aucun robot'));
    return ListView(
      padding: const EdgeInsets.all(16),
      children: robots.robots.map((r) => RobotCard(robot: r)).toList(),
    );
  }
}

class AlertsScreen extends StatelessWidget {
  const AlertsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final alerts = context.watch<AlertsProvider>();
    final theme = Theme.of(context);
    return Column(
      children: [
        if (alerts.unacknowledgedCount > 0)
          Padding(
            padding: const EdgeInsets.all(8),
            child: ElevatedButton.icon(
              onPressed: () => alerts.acknowledgeAll(),
              icon: const Icon(Icons.done_all),
              label: Text('Tout acquitter (${alerts.unacknowledgedCount})'),
            ),
          ),
        Expanded(
          child: alerts.alerts.isEmpty
              ? const Center(child: Text('Aucune alerte'))
              : ListView(
                  children: alerts.alerts.map((a) {
                    final color = a.severity == 'critical' ? Colors.red : a.severity == 'warning' ? Colors.orange : Colors.blue;
                    return ListTile(
                      leading: Icon(a.acknowledged ? Icons.check_circle_outline : Icons.warning, color: a.acknowledged ? Colors.grey : color),
                      title: Text(a.title, style: TextStyle(fontWeight: a.acknowledged ? FontWeight.normal : FontWeight.bold)),
                      subtitle: Text('${a.zone} Â· ${a.message}'),
                      trailing: Text(a.timestamp.substring(11, 19), style: theme.textTheme.bodySmall),
                      onTap: a.acknowledged ? null : () => alerts.acknowledge(a.id),
                    );
                  }).toList(),
                ),
        ),
      ],
    );
  }
}
