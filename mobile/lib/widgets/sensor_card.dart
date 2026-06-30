// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import '../models/sensor.dart';

class SensorCard extends StatelessWidget {
  final Sensor sensor;
  const SensorCard({super.key, required this.sensor});

  IconData _iconForType(String type) {
    switch (type) {
      case 'soil_moisture': return Icons.water_drop;
      case 'air_temp': return Icons.thermostat;
      case 'humidity': return Icons.water;
      case 'ph': return Icons.science;
      case 'light': return Icons.wb_sunny;
      case 'wind': return Icons.air;
      case 'pressure': return Icons.compress;
      default: return Icons.sensors;
    }
  }

  Color _colorForValue(String type, double value) {
    if (type == 'soil_moisture') {
      if (value < 30) return Colors.red;
      if (value < 60) return Colors.orange;
      return Colors.green;
    }
    return Colors.blue;
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: _colorForValue(sensor.type, sensor.value).withValues(alpha: 0.2),
          child: Icon(_iconForType(sensor.type), color: _colorForValue(sensor.type, sensor.value)),
        ),
        title: Text('${sensor.type.replaceAll('_', ' ')} â€” ${sensor.value.toStringAsFixed(1)} ${sensor.unit}'),
        subtitle: Text('${sensor.zone} Â· ${sensor.nodeId} Â· Batterie: ${sensor.battery.toStringAsFixed(0)}%'),
        trailing: Icon(sensor.online ? Icons.wifi : Icons.wifi_off, color: sensor.online ? Colors.green : Colors.grey),
      ),
    );
  }
}
