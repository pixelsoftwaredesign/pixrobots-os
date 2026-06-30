// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';

class HumidityChart extends StatelessWidget {
  final double humidity;
  final double? threshold;
  final double size;

  const HumidityChart({super.key, required this.humidity, this.threshold, this.size = 80});

  Color _color(double h) {
    if (h < 30) return Colors.red;
    if (h < 60) return Colors.orange;
    return Colors.green;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          height: size, width: size,
          child: Stack(
            children: [
              PieChart(PieChartData(sections: [
                PieChartSectionData(value: humidity, color: _color(humidity), radius: size / 3.5, title: '${humidity.toStringAsFixed(0)}%', titleStyle: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                PieChartSectionData(value: 100 - humidity, color: Colors.grey[300], radius: size / 3.5),
              ])),
              if (threshold != null)
                Positioned.fill(
                  child: CustomPaint(painter: _ThresholdPainter(threshold!), size: Size(size, size)),
                ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Text('HumiditÃ©', style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

class _ThresholdPainter extends CustomPainter {
  final double threshold;
  _ThresholdPainter(this.threshold);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.red.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    final angle = (threshold / 100) * 3.14159 * 2 - 3.14159 / 2;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 4;
    canvas.drawLine(center, Offset(center.dx + radius * 0.7 * cos(angle), center.dy + radius * 0.7 * sin(angle)), paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
