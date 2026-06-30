// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'package:flutter/foundation.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  final AuthService _auth = AuthService();
  final ApiService _api = ApiService();
  bool _loading = true;
  bool _authenticated = false;
  String? _error;

  bool get loading => _loading;
  bool get authenticated => _authenticated;
  String? get error => _error;
  AuthService get auth => _auth;
  ApiService get api => _api;

  Future<void> init() async {
    await _auth.load();
    if (_auth.isAuthenticated) {
      _api.setBaseUrl(_auth.serverUrl!);
      _authenticated = true;
    }
    _loading = false;
    notifyListeners();
  }

  Future<bool> login(String serverUrl, {String? apiKey, String? username, String? password}) async {
    _loading = true;
    _error = null;
    notifyListeners();

    final ok = await _auth.login(serverUrl, apiKey: apiKey, username: username, password: password);
    if (ok) {
      await _api.setBaseUrl(serverUrl);
      _authenticated = true;
    } else {
      _error = 'Ã‰chec d\'authentification';
    }
    _loading = false;
    notifyListeners();
    return ok;
  }

  Future<void> logout() async {
    await _auth.logout();
    _authenticated = false;
    notifyListeners();
  }
}
