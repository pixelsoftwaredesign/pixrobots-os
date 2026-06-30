// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _serverCtrl = TextEditingController(text: 'http://');
  final _keyCtrl = TextEditingController();
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  bool _usePassword = false;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.agriculture, size: 80, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 16),
              Text('AgriculApp', style: Theme.of(context).textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.bold)),
              Text('Pixel OS Mobile', style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: Colors.grey)),
              const SizedBox(height: 48),
              TextField(controller: _serverCtrl, decoration: const InputDecoration(labelText: 'URL du serveur Pixel OS', prefixIcon: Icon(Icons.dns), border: OutlineInputBorder())),
              const SizedBox(height: 16),
              if (!_usePassword)
                TextField(controller: _keyCtrl, decoration: const InputDecoration(labelText: 'ClÃ© API PixKey', prefixIcon: Icon(Icons.vpn_key), border: OutlineInputBorder()), obscureText: true),
              if (_usePassword) ...[
                TextField(controller: _userCtrl, decoration: const InputDecoration(labelText: 'Utilisateur', prefixIcon: Icon(Icons.person), border: OutlineInputBorder())),
                const SizedBox(height: 16),
                TextField(controller: _passCtrl, decoration: const InputDecoration(labelText: 'Mot de passe', prefixIcon: Icon(Icons.lock), border: OutlineInputBorder()), obscureText: true),
              ],
              const SizedBox(height: 8),
              TextButton(onPressed: () => setState(() => _usePassword = !_usePassword),
                  child: Text(_usePassword ? 'Utiliser une clÃ© API' : 'Utiliser mot de passe')),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity, height: 48,
                child: ElevatedButton(
                  onPressed: auth.loading ? null : () async {
                    final ok = await auth.login(
                      _serverCtrl.text,
                      apiKey: _usePassword ? null : _keyCtrl.text,
                      username: _usePassword ? _userCtrl.text : null,
                      password: _usePassword ? _passCtrl.text : null,
                    );
                    if (!ok && mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Connexion Ã©chouÃ©e. VÃ©rifiez l\'URL et les identifiants.')),
                      );
                    }
                  },
                  child: auth.loading ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Connexion', style: TextStyle(fontSize: 16)),
                ),
              ),
              if (auth.error != null) Padding(
                padding: const EdgeInsets.only(top: 16),
                child: Text(auth.error!, style: const TextStyle(color: Colors.red)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _serverCtrl.dispose();
    _keyCtrl.dispose();
    _userCtrl.dispose();
    _passCtrl.dispose();
    super.dispose();
  }
}
