// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/mqtt_service.dart';
import 'providers/auth_provider.dart';
import 'providers/sensors_provider.dart';
import 'providers/robots_provider.dart';
import 'providers/alerts_provider.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AgriculApp());
}

class AgriculApp extends StatelessWidget {
  const AgriculApp({super.key});

  @override
  Widget build(BuildContext context) {
    final mqtt = MqttService();
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProxyProvider<AuthProvider, SensorsProvider>(
          create: (ctx) => SensorsProvider(ctx.read<AuthProvider>().api, mqtt),
          update: (_, auth, prev) => prev!,
        ),
        ChangeNotifierProxyProvider<AuthProvider, RobotsProvider>(
          create: (ctx) => RobotsProvider(ctx.read<AuthProvider>().api, mqtt),
          update: (_, auth, prev) => prev!,
        ),
        ChangeNotifierProxyProvider<AuthProvider, AlertsProvider>(
          create: (ctx) => AlertsProvider(ctx.read<AuthProvider>().api, mqtt),
          update: (_, auth, prev) => prev!,
        ),
      ],
      child: MaterialApp(
        title: 'AgriculApp',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorSchemeSeed: Colors.green,
          useMaterial3: true,
          brightness: Brightness.light,
        ),
        home: const AuthGate(),
      ),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    context.read<AuthProvider>().init();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    if (auth.loading) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (!auth.authenticated) {
      return const LoginScreen();
    }
    return const DashboardScreen();
  }
}
