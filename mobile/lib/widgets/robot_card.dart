// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import '../models/robot.dart';
import '../screens/missions_screen.dart';

class RobotCard extends StatelessWidget {
  final Robot robot;
  const RobotCard({super.key, required this.robot});

  Color _statusColor(String status) {
    switch (status) {
      case 'idle': return Colors.grey;
      case 'executing': return Colors.blue;
      case 'charging': return Colors.green;
      case 'error': return Colors.red;
      case 'safe_return': return Colors.orange;
      default: return Colors.grey;
    }
  }

  IconData _roleIcon(String role) {
    switch (role) {
      case 'inspecteur': return Icons.search;
      case 'transporteur': return Icons.local_shipping;
      case 'recolteur': return Icons.handyman;
      case 'drone': return Icons.flight;
      default: return Icons.smart_toy;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: _statusColor(robot.status).withValues(alpha: 0.2),
          child: Icon(_roleIcon(robot.role), color: _statusColor(robot.status)),
        ),
        title: Text(robot.name, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${robot.role} Â· Batterie: ${robot.battery.toStringAsFixed(0)}%'),
            if (robot.currentMission != null) Text('Mission: ${robot.currentMission}', style: const TextStyle(fontSize: 12)),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(color: _statusColor(robot.status).withValues(alpha: 0.2), borderRadius: BorderRadius.circular(4)),
              child: Text(robot.status, style: TextStyle(color: _statusColor(robot.status), fontSize: 12)),
            ),
            const SizedBox(width: 4),
            Icon(robot.online ? Icons.wifi : Icons.wifi_off, color: robot.online ? Colors.green : Colors.grey, size: 18),
          ],
        ),
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => MissionsScreen(robot: robot))),
      ),
    );
  }
}
