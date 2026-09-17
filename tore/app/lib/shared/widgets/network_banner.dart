import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config/remote_config.dart';
import '../../core/network/network_state_provider.dart';

class ToreNetworkBanner extends ConsumerWidget {
  const ToreNetworkBanner({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final remoteMessage = ref.watch(remoteWriteMessageProvider);
    if (remoteMessage != null) {
      return _StatusBanner(
        icon: Icons.lock_clock_outlined,
        background: Colors.amber.shade100,
        border: Colors.amber.shade400,
        text: remoteMessage,
      );
    }

    final snapshot = ref.watch(networkStateProvider);
    final isOnline = snapshot.state == NetworkState.online;
    final isOffline = snapshot.state == NetworkState.offline;
    if (isOnline) return const SizedBox.shrink();

    return _StatusBanner(
      icon: isOffline ? Icons.cloud_off : Icons.wifi_tethering_error_rounded,
      background: isOffline ? Colors.red.shade100 : Colors.orange.shade100,
      border: isOffline ? Colors.red.shade300 : Colors.orange.shade300,
      text: isOffline
          ? 'Hors ligne — mode lecture.'
          : 'Réseau instable — certaines données peuvent dater.',
      action: TextButton(
        onPressed: () async {
          await ref.read(networkStateProvider.notifier).refresh();
        },
        child: const Text('Réessayer'),
      ),
    );
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({
    required this.icon,
    required this.background,
    required this.border,
    required this.text,
    this.action,
  });

  final IconData icon;
  final Color background;
  final Color border;
  final String text;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: background,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          border: Border(bottom: BorderSide(color: border)),
        ),
        child: Row(
          children: [
            Icon(icon),
            const SizedBox(width: 8),
            Expanded(child: Text(text)),
            if (action != null) action!,
          ],
        ),
      ),
    );
  }
}
