import 'package:dio/dio.dart';
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
          error: (error, _) => _JoinErrorState(
            reasonCode: _joinErrorCode(error),
            message: _joinErrorMessage(error),
            onRetry: () => ref.invalidate(_eventDetailsProvider(eventId)),
          ),
          data: (event) => configAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => _JoinErrorState(
              reasonCode: _joinErrorCode(error),
              message: _joinErrorMessage(error),
              onRetry: () => ref.invalidate(eventConfigProvider(eventId)),
            ),
            data: (cfg) =>
                _JoinEventContent(event: event, config: cfg, eventId: eventId),
          ),
        ),
      ),
    );
  }
}

class _JoinEventContent extends ConsumerWidget {
  const _JoinEventContent(
      {required this.event, required this.config, required this.eventId});

  final Map<String, dynamic> event;
  final dynamic config;
  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventName = (event['name'] ?? 'Event #$eventId').toString();
    final modules = <String, bool>{
      'menu': config.menuEnabled,
      'wallet': config.walletEnabled,
      'polymarket': config.polymarketEnabled,
      'ticker': config.menuEnabled ||
          config.walletEnabled ||
          config.polymarketEnabled,
    };
    final visibleModules =
        modules.entries.where((e) => e.value).map((e) => e.key).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(eventName, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 6),
        Text('Event #$eventId', style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 18),
        Text('Modules actifs', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: visibleModules
              .map((m) => Chip(
                  avatar: Icon(_iconForModule(m), size: 18),
                  label: Text(_labelForModule(m))))
              .toList(),
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
          child: const Text('Confirmer join'),
        ),
      ],
    );
  }
}

class _JoinErrorState extends StatelessWidget {
  const _JoinErrorState(
      {required this.reasonCode, required this.message, required this.onRetry});

  final String reasonCode;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.warning_amber_rounded, size: 44),
          const SizedBox(height: 10),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 6),
          Text('Code: $reasonCode',
              style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 16),
          OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Réessayer')),
        ],
      ),
    );
  }
}

final _eventDetailsProvider =
    FutureProvider.family<Map<String, dynamic>, int>((ref, eventId) async {
  return ref.read(apiProvider).event(eventId);
});

String _joinErrorCode(Object error) {
  if (error is DioException) {
    final detail = error.response?.data;
    if (detail is Map && detail['detail'] is Map) {
      final reason = (detail['detail'] as Map)['reason']?.toString();
      if (reason != null && reason.isNotEmpty) return reason;
    }
    if (error.response?.statusCode == 403) return 'forbidden';
    if (error.response?.statusCode == 404) return 'invalid';
  }
  return 'invalid';
}

String _joinErrorMessage(Object error) {
  switch (_joinErrorCode(error)) {
    case 'invalid':
    case 'expired':
      return 'QR invalid/expiré.';
    case 'forbidden':
      return 'Accès interdit.';
    case 'module_off':
      return 'Module OFF pour cet event.';
    case 'event_paused':
      return 'Event en pause.';
    default:
      return 'Impossible de rejoindre cet event.';
  }
}

IconData _iconForModule(String module) {
  switch (module) {
    case 'menu':
      return Icons.restaurant_menu;
    case 'wallet':
      return Icons.account_balance_wallet_outlined;
    case 'polymarket':
      return Icons.meeting_room_outlined;
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
      return 'Rooms';
    case 'ticker':
      return 'Ticker';
    default:
      return module;
  }
}
