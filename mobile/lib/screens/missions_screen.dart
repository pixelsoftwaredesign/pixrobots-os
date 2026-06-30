// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/robots_provider.dart';
import '../models/robot.dart';

class MissionsScreen extends StatefulWidget {
  final Robot? robot;
  const MissionsScreen({super.key, this.robot});

  @override
  State<MissionsScreen> createState() => _MissionsScreenState();
}

class _MissionsScreenState extends State<MissionsScreen> {
  final _zoneCtrl = TextEditingController();
  final _actionsCtrl = TextEditingController();
  String? _selectedRobotId;

  @override
  void initState() {
    super.initState();
    _selectedRobotId = widget.robot?.id;
  }

  @override
  Widget build(BuildContext context) {
    final robotsProv = context.watch<RobotsProvider>();
    final missions = widget.robot != null
        ? robotsProv.missions.where((m) => m.robotId == widget.robot!.id).toList()
        : robotsProv.missions;
    final robots = robotsProv.robots;

    return Scaffold(
      appBar: AppBar(title: Text(widget.robot != null ? 'Missions Â· ${widget.robot!.name}' : 'Missions')),
      floatingActionButton: FloatingActionButton(
        child: const Icon(Icons.add),
        onPressed: () => _showCreateDialog(context, robots, robotsProv),
      ),
      body: missions.isEmpty
          ? const Center(child: Text('Aucune mission'))
          : ListView(
              padding: const EdgeInsets.all(16),
              children: missions.map((m) {
                Color statusColor;
                switch (m.status) {
                  case 'completed': statusColor = Colors.green;
                  case 'in_progress': statusColor = Colors.blue;
                  case 'failed': statusColor = Colors.red;
                  default: statusColor = Colors.orange;
                }
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: Icon(Icons.task_alt, color: statusColor),
                    title: Text('${m.id} Â· ${m.zone}'),
                    subtitle: Text('${m.robotName} Â· ${m.actions.join(", ")}'),
                    trailing: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(4)),
                      child: Text(m.status, style: TextStyle(color: statusColor, fontSize: 12)),
                    ),
                  ),
                );
              }).toList(),
            ),
    );
  }

  void _showCreateDialog(BuildContext context, List<Robot> robots, RobotsProvider prov) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('Nouvelle mission'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          DropdownButtonFormField<String>(
            value: _selectedRobotId ?? (robots.isNotEmpty ? robots.first.id : null),
            decoration: const InputDecoration(labelText: 'Robot'),
            items: robots.map((r) => DropdownMenuItem(value: r.id, child: Text(r.name))).toList(),
            onChanged: (v) => _selectedRobotId = v,
          ),
          TextField(controller: _zoneCtrl, decoration: const InputDecoration(labelText: 'Zone')),
          TextField(controller: _actionsCtrl, decoration: const InputDecoration(labelText: 'Actions (virgule)'), maxLines: 2),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
        ElevatedButton(onPressed: () async {
          if (_selectedRobotId == null) return;
          await prov.sendMission(
            _selectedRobotId!,
            _zoneCtrl.text,
            _actionsCtrl.text.split(',').map((a) => a.trim()).where((a) => a.isNotEmpty).toList(),
          );
          if (ctx.mounted) Navigator.pop(ctx);
        }, child: const Text('Envoyer')),
      ],
    ));
  }

  @override
  void dispose() {
    _zoneCtrl.dispose();
    _actionsCtrl.dispose();
    super.dispose();
  }
}
