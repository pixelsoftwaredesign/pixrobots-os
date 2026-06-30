// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      appBar: AppBar(title: const Text('ParamÃ¨tres')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Serveur Pixel OS', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text(auth.auth.serverUrl ?? 'Non connectÃ©'),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: () => auth.logout(),
                    icon: const Icon(Icons.logout),
                    label: const Text('DÃ©connexion'),
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.red, foregroundColor: Colors.white),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Ã€ propos', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  const Text('AgriculApp v2.0.0'),
                  const Text('Pixel OS Mobile Client'),
                  const SizedBox(height: 8),
                  Text('Â© 2026 Pixel Software Design', style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
