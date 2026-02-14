import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../../state.dart';
import '../../events/presentation/event_config_providers.dart';

class JoinEventConfirmScreen extends ConsumerWidget {
  const JoinEventConfirmScreen({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventAsync = ref.watch(_eventDetailsProvider(eventId));
    final configAsync = ref.watch(eventConfigProvider(eventId));

    return Scaffold(
      appBar: AppBar(title: const Text('Rejoindre un event')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: eventAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => const Center(child: Text('Event introuvable.')),
          data: (event) {
            final eventName = (event['name'] ?? 'Event #$eventId').toString();
            final modules = configAsync.maybeWhen(
              data: (cfg) => <String, bool>{
                'menu': cfg.menuEnabled,
                'wallet': cfg.walletEnabled,
                'polymarket': cfg.polymarketEnabled,
                'ticker': cfg.menuEnabled || cfg.walletEnabled || cfg.polymarketEnabled,
              },
              orElse: () => const <String, bool>{},
            );
            final visibleModules = modules.entries.where((e) => e.value).map((e) => e.key).toList();

            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(eventName, style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 6),
                Text('Event #$eventId', style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 18),
                Text('Modules disponibles', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: visibleModules.isEmpty
                      ? [const Chip(label: Text('Aucun module actif'))]
                      : visibleModules.map((m) => Chip(avatar: Icon(_iconForModule(m), size: 18), label: Text(_labelForModule(m)))).toList(),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: () {
                    ref.read(appContextProvider.notifier).enterEvent(
                      eventId: eventId,
                      eventName: eventName,
                      activeEventModules: modules,
                    );
                    Navigator.of(context).popUntil((route) => route.isFirst);
                  },
                  child: const Text('Rejoindre'),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

final _eventDetailsProvider = FutureProvider.family<Map<String, dynamic>, int>((ref, eventId) async {
  return ref.read(apiProvider).event(eventId);
});

IconData _iconForModule(String module) {
  switch (module) {
    case 'menu':
      return Icons.restaurant_menu;
    case 'wallet':
      return Icons.account_balance_wallet_outlined;
    case 'polymarket':
      return Icons.casino_outlined;
    case 'ticker':
      return Icons.toll_outlined;
    default:
      return Icons.widgets_outlined;
  }
}

String _labelForModule(String module) {
  switch (module) {
    case 'menu':
      return 'Menu';
    case 'wallet':
      return 'Wallet';
    case 'polymarket':
      return 'Polymarket';
    case 'ticker':
      return 'Ticker';
    default:
      return module;
  }
}
