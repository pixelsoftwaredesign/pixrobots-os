// Pixel OS - Copyright 2026
// Free License - Verifiable and Reliable for Internet Users
import 'dart:async';
import 'dart:convert';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

typedef MessageCallback = void Function(String topic, Map<String, dynamic> payload);

class MqttService {
  MqttServerClient? _client;
  final List<MessageCallback> _callbacks = [];
  StreamSubscription? _subscription;
  bool _connected = false;

  bool get isConnected => _connected;

  void onMessage(MessageCallback cb) => _callbacks.add(cb);

  Future<void> connect(String server, {int port = 1883, String? username, String? password}) async {
    _client = MqttServerClient(server, 'agriculapp_${DateTime.now().millisecondsSinceEpoch}');
    _client!.port = port;
    _client!.keepAlivePeriod = 30;
    _client!.logging(on: false);

    final connMessage = MqttConnectMessage()
        .withWillTopic('agriculapp/disconnected')
        .withWillMessage('{"online": false}')
        .startClean()
        .withWillQos(MqttQos.atLeastOnce);
    _client!.connectionMessage = connMessage;

    try {
      await _client!.connect(username ?? '', password ?? '');
    } catch (e) {
      _connected = false;
      rethrow;
    }

    _connected = true;
    _client!.updates!.listen(_onData);
    subscribe('sensors/+/+');
    subscribe('robots/+/status');
    subscribe('alerts/#');
  }

  void _onData(List<MqttReceivedMessage<MqttMessage>>? messages) {
    if (messages == null) return;
    for (final msg in messages) {
      final topic = msg.topic;
      final payload = msg.payload as MqttPublishMessage;
      final bytes = payload.payload.message;
      final decoded = utf8.decode(bytes);
      try {
        final json = jsonDecode(decoded) as Map<String, dynamic>;
        for (final cb in _callbacks) {
          cb(topic, json);
        }
      } catch (_) {}
    }
  }

  void subscribe(String topic) {
    _client?.subscribe(topic, MqttQos.atLeastOnce);
  }

  Future<void> publish(String topic, Map<String, dynamic> payload) async {
    if (!_connected || _client == null) return;
    final builder = MqttClientPayloadBuilder();
    builder.addString(jsonEncode(payload));
    _client!.publishMessage(topic, MqttQos.atLeastOnce, builder.payload!);
  }

  Future<void> disconnect() async {
    await _subscription?.cancel();
    _client?.disconnect();
    _connected = false;
  }
}
