// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  static const _tokenKey = 'pixkey_token';
  static const _serverKey = 'pixos_server';

  String? _token;
  String? _serverUrl;

  bool get isAuthenticated => _token != null;
  String? get serverUrl => _serverUrl;

  Future<void> load() async {
    _token = await _storage.read(key: _tokenKey);
    _serverUrl = await _storage.read(key: _serverKey);
  }

  Future<bool> login(String serverUrl, {String? apiKey, String? username, String? password}) async {
    _serverUrl = serverUrl;
    final url = '$serverUrl/api/auth/login';
    final body = <String, dynamic>{};
    if (apiKey != null) {
      body['api_key'] = apiKey;
    } else if (username != null && password != null) {
      body['username'] = username;
      body['password'] = password;
    } else {
      return false;
    }

    try {
      final response = await http.post(Uri.parse(url),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _token = data['token'];
        await _storage.write(key: _tokenKey, value: _token);
        await _storage.write(key: _serverKey, value: serverUrl);
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<bool> loginWithQr(String qrData) async {
    try {
      final data = jsonDecode(qrData);
      final server = data['server'];
      final key = data['key'];
      return await login(server, apiKey: key);
    } catch (_) {
      return false;
    }
  }

  Future<void> logout() async {
    _token = null;
    _serverUrl = null;
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _serverKey);
  }

  Map<String, String> authHeaders() {
    if (_token != null) {
      return {'Authorization': 'Bearer $_token', 'Content-Type': 'application/json'};
    }
    return {'Content-Type': 'application/json'};
  }
}
