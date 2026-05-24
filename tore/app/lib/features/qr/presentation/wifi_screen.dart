import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';

class WifiScreen extends ConsumerStatefulWidget {
  const WifiScreen({super.key, required this.eventId, required this.token});

  final int eventId;
  final String token;

  @override
  ConsumerState<WifiScreen> createState() => _WifiScreenState();
}

class _WifiScreenState extends ConsumerState<WifiScreen> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = ref
        .read(apiProvider)
        .eventWifiClaim(eventId: widget.eventId, token: widget.token);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('WiFi event')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Accès WiFi refusé: ${snap.error}'));
          }
          final data = snap.data ?? const <String, dynamic>{};
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text('SSID: ${data['ssid'] ?? ''}',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              SelectableText('Password: ${data['password'] ?? ''}'),
              const SizedBox(height: 8),
              if ((data['instructions'] ?? '').toString().isNotEmpty)
                Text((data['instructions'] ?? '').toString()),
              const SizedBox(height: 8),
              Text('Expires: ${(data['expiresAt'] ?? '').toString()}'),
            ],
          );
        },
      ),
    );
  }
}
