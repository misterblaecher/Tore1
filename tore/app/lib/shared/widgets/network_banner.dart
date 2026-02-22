import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/network_state_provider.dart';
import '../../state.dart';

class ToreNetworkBanner extends ConsumerWidget {
  const ToreNetworkBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final snapshot = ref.watch(networkStateProvider);
    final isOnline = snapshot.state == NetworkState.online;
    final isOffline = snapshot.state == NetworkState.offline;
    final bg = isOnline
        ? const Color(0x2200C853)
        : (isOffline ? Colors.red.shade100 : Colors.orange.shade100);
    final border = isOnline
        ? const Color(0x6600C853)
        : (isOffline ? Colors.red.shade300 : Colors.orange.shade300);
    final text = isOnline
        ? 'ONLINE'
        : (isOffline ? 'OFFLINE — mode lecture.' : 'DEGRADED — réseau instable.');

    return Material(
      color: bg,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(border: Border(bottom: BorderSide(color: border))),
        child: Row(
          children: [
            Icon(isOnline ? Icons.wifi : (isOffline ? Icons.cloud_off : Icons.wifi_tethering_error_rounded)),
            const SizedBox(width: 8),
            Expanded(child: Text(text)),
            if (!isOnline)
              TextButton(
                onPressed: () async {
                  await ref.read(networkStateProvider.notifier).refresh();
                  await ref.read(appBootProvider.notifier).bootstrap();
                },
                child: const Text('Retry'),
              ),
          ],
        ),
      ),
    );
  }
}
