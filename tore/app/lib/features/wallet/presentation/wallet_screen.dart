import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../state.dart';
import '../../../shared/utils/user_display.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import 'package:flutter/foundation.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../wallet_providers.dart';
import '../wallet_models.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../qr/presentation/module_unavailable_screen.dart';

class WalletScreen extends ConsumerStatefulWidget {
  const WalletScreen({super.key, required this.eventId});
  final int eventId;

  @override
  ConsumerState<WalletScreen> createState() => _WalletScreenState();
}

class _WalletScreenState extends ConsumerState<WalletScreen> {
  late Future<Map<String, dynamic>> _future;

  bool _didLoadWithUser = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Map<String, dynamic>> _load() {
    final api = ref.read(apiProvider);
    final userId = ref.read(userIdProvider);

    if (userId == null) {
      return Future.value(const <String, dynamic>{});
    }

    return api.walletMe().timeout(const Duration(seconds: 6));
  }

  void _refresh() {
    setState(() {
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final meAsync = ref.watch(meProvider);
    final api = ref.watch(apiProvider);
    final userId = ref.watch(userIdProvider);
    final configAsync = ref.watch(eventConfigProvider(widget.eventId));
    final eventAsync = ref.watch(_eventDetailsProvider(widget.eventId));
    final eventState = eventAsync.maybeWhen(data: _readEventState, orElse: () => 'LIVE');
    final writeBlocked = isWriteBlockedByEventState(eventState);
    final config = configAsync.maybeWhen(
      data: (value) => value,
      orElse: () => null,
    );

    final walletQrDeepLink = 'tore://user?uid=$userId&event_id=${widget.eventId}';

    if (config != null && !config.walletEnabled) {
      return const ModuleUnavailableScreen(
        title: 'Wallet indisponible',
        message: 'Ce module est désactivé pour cet event.',
        reasonCode: 'module_off',
      );
    }

    if (userId == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    final userLabel = meAsync.maybeWhen(
      data: (me) => UserDisplay.labelWithCode(me),
      orElse: () => 'Invité #${UserDisplay.shortCode(userId)}',
    );

    if (!_didLoadWithUser) {
      _didLoadWithUser = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Portefeuille')),
      body: RefreshIndicator(
        onRefresh: () async {
          _refresh();
          ref.invalidate(walletHistoryProvider(
            WalletHistoryArgs(eventId: widget.eventId, userId: userId),
          ));
        },
        child: FutureBuilder<Map<String, dynamic>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return ListView(
                children: const [
                  SizedBox(height: 240),
                  Center(child: CircularProgressIndicator()),
                ],
              );
            }
            if (snap.hasError) {
              return ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Center(child: Text(ErrorMapper.message(snap.error as Object))),
                  const SizedBox(height: 8),
                  OutlinedButton(onPressed: _refresh, child: const Text('Réessayer')),
                ],
              );
            }

            final data = snap.data ?? const {};
            final balanceValue = data['balance'] ?? data['tickets'] ?? data['amount'] ?? data['value'] ?? 0;
            final balance = balanceValue.toString();

            final historyAsync = ref.watch(
              walletHistoryProvider(WalletHistoryArgs(eventId: widget.eventId, userId: userId)),
            );

            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (writeBlocked)
                  _WriteBlockedBanner(message: writeBlockedReasonMessage(eventState)),
                Text(
                  'Tickets: $balance',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 12),
                Text(
                  'Event: #${widget.eventId}\nUtilisateur: $userLabel',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('My Wallet QR', style: Theme.of(context).textTheme.titleMedium),
                        const SizedBox(height: 8),
                        Center(
                          child: QrImageView(
                            data: walletQrDeepLink,
                            size: 170,
                          ),
                        ),
                        const SizedBox(height: 8),
                        SelectableText(walletQrDeepLink, style: Theme.of(context).textTheme.bodySmall),
                        const SizedBox(height: 8),
                        OutlinedButton.icon(
                          onPressed: () async {
                            await Clipboard.setData(ClipboardData(text: walletQrDeepLink));
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('QR link copié')),
                            );
                          },
                          icon: const Icon(Icons.copy_outlined),
                          label: const Text('Copy'),
                        ),
                      ],
                    ),
                  ),
                ),
                if (kDebugMode)
                  ElevatedButton(
                    onPressed: () async {
                      try {
                        await api.creditTickets(
                          eventId: widget.eventId,
                          userId: userId,
                          delta: 10,
                        );

                        if (!context.mounted) return;

                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('✅ +10 tickets crédités')),
                        );

                        _refresh();
                      } catch (e) {
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Erreur crédit: ${ErrorMapper.message(e)}')),
                        );
                      }
                    },
                    child: const Text('Ajouter 10 tickets'),
                  ),
                const SizedBox(height: 8),
                ElevatedButton(
                  onPressed: writeBlocked
                      ? null
                      : () async {
                          final toCtrl = TextEditingController();
                          final amountCtrl = TextEditingController(text: '1');
                          final result = await showDialog<bool>(
                            context: context,
                            builder: (ctx) => AlertDialog(
                              title: const Text('Send Gift'),
                              content: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  TextField(controller: toCtrl, decoration: const InputDecoration(labelText: 'User ID')),
                                  TextField(controller: amountCtrl, decoration: const InputDecoration(labelText: 'Amount')),
                                ],
                              ),
                              actions: [
                                TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                                ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Send')),
                              ],
                            ),
                          );
                          if (result != true) return;
                          try {
                            final toUser = toCtrl.text.trim();
                            final amount = int.tryParse(amountCtrl.text.trim()) ?? 0;
                            await api.walletGift(
                              eventId: widget.eventId,
                              toUserId: toUser,
                              amountCents: amount,
                              idempotencyKey: 'gift-${widget.eventId}-$userId-$toUser-$amount',
                            );
                            _refresh();
                            ref.invalidate(walletHistoryProvider(WalletHistoryArgs(eventId: widget.eventId, userId: userId)));
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Gift envoyé')));
                          } catch (e) {
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(ErrorMapper.message(e))));
                          }
                        },
                  child: const Text('Send Gift'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: _refresh,
                  child: const Text('Rafraîchir'),
                ),
                const SizedBox(height: 18),
                Text(
                  'Historique',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                historyAsync.when(
                  loading: () => const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Center(child: CircularProgressIndicator()),
                  ),
                  error: (e, _) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      ErrorMapper.isNotFound(e)
                          ? 'Historique indisponible.'
                          : 'Historique indisponible: ${ErrorMapper.message(e)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                  data: (entries) {
                    if (entries.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.symmetric(vertical: 10),
                        child: Text('Aucun mouvement pour l’instant.'),
                      );
                    }
                    return Column(
                      children: entries.take(50).map((e) => _HistoryTile(entry: e)).toList(),
                    );
                  },
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  final WalletHistoryEntry entry;
  const _HistoryTile({required this.entry});

  String _fmtTs(BuildContext context, DateTime ts) {
    final t = TimeOfDay.fromDateTime(ts).format(context);
    return '${ts.day.toString().padLeft(2, '0')}/${ts.month.toString().padLeft(2, '0')} $t';
  }

  IconData _icon(String type, int delta) {
    switch (type) {
      case 'order':
        return Icons.shopping_bag_outlined;
      case 'checkin':
        return Icons.qr_code_scanner_outlined;
      case 'admin_credit':
      case 'credit':
        return Icons.add_circle_outline;
      case 'debit':
        return Icons.remove_circle_outline;
      default:
        return delta >= 0 ? Icons.add_circle_outline : Icons.remove_circle_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final delta = entry.delta;
    final sign = delta >= 0 ? '+' : '';
    final time = _fmtTs(context, entry.ts);
    final subtitle = entry.note ?? entry.type;
    final trailing = entry.balanceAfter == null ? '$sign$delta' : '$sign$delta  →  ${entry.balanceAfter}';

    return Card(
      child: ListTile(
        leading: Icon(_icon(entry.type, delta)),
        title: Text(trailing, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('$subtitle\n$time'),
        isThreeLine: true,
      ),
    );
  }
}

class _WriteBlockedBanner extends StatelessWidget {
  const _WriteBlockedBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: Colors.red.shade100,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: Row(
            children: [
              const Icon(Icons.lock_clock_outlined),
              const SizedBox(width: 8),
              Expanded(child: Text(message)),
            ],
          ),
        ),
      ),
    );
  }
}

final _eventDetailsProvider = FutureProvider.family<Map<String, dynamic>, int>((ref, eventId) async {
  return ref.read(apiProvider).event(eventId);
});

String _readEventState(Map<String, dynamic> event) {
  final value = (event['state'] ?? event['status'] ?? event['event_state'] ?? 'LIVE').toString().toUpperCase();
  return value;
}
