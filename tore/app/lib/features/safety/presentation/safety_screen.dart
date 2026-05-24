import 'dart:math';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/error_mapper.dart';
import '../../../state.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/utils/write_gate.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_cta.dart';
import '../../../ui/components/tore_divider.dart';
import '../../../ui/components/tore_list_row.dart';
import '../../events/presentation/active_event_context_provider.dart';
import '../safety_models.dart';
import 'safety_providers.dart';

class SafetyScreen extends ConsumerStatefulWidget {
  const SafetyScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<SafetyScreen> createState() => _SafetyScreenState();
}

class _SafetyScreenState extends ConsumerState<SafetyScreen> {
  final TextEditingController _buddyController = TextEditingController();
  bool _buddyBusy = false;
  bool _okBusy = false;
  bool _panicBusy = false;
  SafetyHistoryItem? _optimisticMyLastCheckin;
  String? _optimisticBuddyId;

  @override
  void dispose() {
    _buddyController.dispose();
    super.dispose();
  }

  String _idempotencyKey(String action) {
    final random = Random().nextInt(1 << 32).toRadixString(16);
    return 'safety-$action-${DateTime.now().microsecondsSinceEpoch}-$random';
  }

  Future<void> _setBuddy() async {
    final eventState =
        ref.read(activeEventContextProvider).valueOrNull?.eventState;
    final blocked = writeDisabledReason(ref,
        intent: WriteIntent.critical, runtimeState: eventState);
    if (blocked != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(blocked)));
      return;
    }

    final buddyUserId = _buddyController.text.trim();
    if (buddyUserId.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Entre un ID buddy.')));
      return;
    }

    setState(() => _buddyBusy = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiProvider).setSafetyBuddy(
            eventId: widget.eventId,
            buddyUserId: buddyUserId,
            idempotencyKey: _idempotencyKey('buddy'),
          );
      if (!messenger.mounted) return;
      HapticFeedback.mediumImpact();
      setState(() => _optimisticBuddyId = buddyUserId);
      ref.invalidate(safetyStateProvider(widget.eventId));
      ref.invalidate(safetyHistoryProvider(widget.eventId));
      messenger.showSnackBar(const SnackBar(content: Text('Buddy défini ✅')));
    } on DioException catch (e) {
      if (!messenger.mounted) return;
      HapticFeedback.heavyImpact();
      messenger.showSnackBar(SnackBar(content: Text(ErrorMapper.message(e))));
    } finally {
      if (mounted) setState(() => _buddyBusy = false);
    }
  }

  Future<void> _checkin(String type) async {
    final eventState =
        ref.read(activeEventContextProvider).valueOrNull?.eventState;
    final blocked = writeDisabledReason(ref,
        intent: WriteIntent.critical, runtimeState: eventState);
    if (blocked != null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(blocked)));
      return;
    }

    final panic = type == 'PANIC';
    setState(() {
      if (panic) {
        _panicBusy = true;
      } else {
        _okBusy = true;
      }
    });
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref.read(apiProvider).safetyCheckin(
            eventId: widget.eventId,
            type: type,
            idempotencyKey: _idempotencyKey(type.toLowerCase()),
          );
      if (!messenger.mounted) return;
      HapticFeedback.lightImpact();
      setState(() => _optimisticMyLastCheckin =
          SafetyHistoryItem(type: type, createdAt: DateTime.now().toUtc()));
      ref.invalidate(safetyStateProvider(widget.eventId));
      ref.invalidate(safetyHistoryProvider(widget.eventId));
      messenger.showSnackBar(SnackBar(
          content: Text(type == 'OK'
              ? 'Check-in OK envoyé ✅'
              : 'Alerte PANIC envoyée 🚨')));
    } on DioException catch (e) {
      if (!messenger.mounted) return;
      HapticFeedback.heavyImpact();
      final runtime = ErrorMapper.runtimeBlockedMessage(e);
      messenger.showSnackBar(
          SnackBar(content: Text(runtime ?? ErrorMapper.message(e))));
    } finally {
      if (mounted) {
        setState(() {
          _okBusy = false;
          _panicBusy = false;
        });
      }
    }
  }

  Future<void> _confirmPanic() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('JE VEUX PARTIR'),
        content: const Text('Tu veux prévenir l’orga ?'),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Annuler')),
          TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Confirmer')),
        ],
      ),
    );
    if (confirmed == true) {
      await _checkin('PANIC');
    }
  }

  Future<void> _callOrga(String number) async {
    final uri = Uri(scheme: 'tel', path: number);
    final messenger = ScaffoldMessenger.of(context);
    if (!await launchUrl(uri)) {
      if (!messenger.mounted) return;
      messenger.showSnackBar(
          const SnackBar(content: Text('Impossible d’ouvrir le téléphone.')));
    }
  }

  String _relative(DateTime? date) {
    if (date == null) return '—';
    final d = DateTime.now().toUtc().difference(date.toUtc());
    if (d.inMinutes < 1) return 'à l’instant';
    if (d.inMinutes < 60) return 'il y a ${d.inMinutes} min';
    if (d.inHours < 24) return 'il y a ${d.inHours} h';
    return 'il y a ${d.inDays} j';
  }

  @override
  Widget build(BuildContext context) {
    final stateAsync = ref.watch(safetyStateProvider(widget.eventId));
    final historyAsync = ref.watch(safetyHistoryProvider(widget.eventId));
    final eventCtx = ref.watch(activeEventContextProvider).valueOrNull;

    final runtimeState = eventCtx?.eventState;
    final readOnly = isReadOnly(ref);
    final degradedBlocked = isWriteDegradedBlocked(ref, WriteIntent.critical);
    final runtimeBlocked = isWriteBlockedByEventState(runtimeState);
    final blockedReason = writeBlockedMessage(
      readOnly: readOnly,
      degradedBlocked: degradedBlocked,
      runtimeState: runtimeState,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Safe Kit')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (readOnly || degradedBlocked || runtimeBlocked)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ServiceLimitedBanner(message: blockedReason),
            ),
          ToreCard(
            header: const Text('Contacts ORGA',
                style: TextStyle(fontWeight: FontWeight.w700)),
            child: stateAsync.when(
              data: (data) {
                final phone = data.data.orgaPhone;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ToreListRow(
                      title: phone == null || phone.isEmpty
                          ? 'Numéro indisponible'
                          : phone,
                      subtitle:
                          data.data.messageHint ?? 'Aucun message particulier.',
                      trailing: phone == null || phone.isEmpty
                          ? null
                          : const Icon(Icons.call_outlined),
                      onTap: phone == null || phone.isEmpty
                          ? null
                          : () => _callOrga(phone),
                    ),
                  ],
                );
              },
              loading: () => const Padding(
                  padding: EdgeInsets.all(12),
                  child: CircularProgressIndicator()),
              error: (_, __) =>
                  const Text('Impossible de charger les contacts ORGA.'),
            ),
          ),
          const SizedBox(height: 12),
          ToreCard(
            header: const Text('Buddy',
                style: TextStyle(fontWeight: FontWeight.w700)),
            child: stateAsync.when(
              data: (stateData) {
                final buddy = _optimisticBuddyId ?? stateData.data.myBuddy?.id;
                final buddyLabel = stateData.data.myBuddy?.displayNameMasked ??
                    buddy ??
                    'Aucun buddy';
                final buddyLast = stateData.data.buddyLastCheckin;
                final myLast =
                    _optimisticMyLastCheckin ?? stateData.data.myLastCheckin;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        ToreChip(
                            label:
                                stateData.data.enabled ? 'Actif' : 'Désactivé',
                            variant: stateData.data.enabled
                                ? ToreChipVariant.ok
                                : ToreChipVariant.warn),
                        const SizedBox(width: 8),
                        Expanded(child: Text('Mon buddy: $buddyLabel')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                        'Mon dernier check-in: ${myLast == null ? '—' : '${myLast.type} · ${_relative(myLast.createdAt)}'}'),
                    const SizedBox(height: 4),
                    Text(
                        'Dernier check-in buddy: ${buddyLast == null ? '—' : '${buddyLast.type} · ${_relative(buddyLast.createdAt)}'}'),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _buddyController,
                      decoration:
                          const InputDecoration(labelText: 'Entrer l’ID buddy'),
                      textInputAction: TextInputAction.done,
                    ),
                    const SizedBox(height: 8),
                    ToreCTA(
                        label: 'Définir buddy',
                        onPressed: _buddyBusy ? null : _setBuddy,
                        busy: _buddyBusy),
                  ],
                );
              },
              loading: () => const Padding(
                  padding: EdgeInsets.all(12),
                  child: CircularProgressIndicator()),
              error: (_, __) =>
                  const Text('Impossible de charger les infos buddy.'),
            ),
          ),
          const SizedBox(height: 12),
          ToreCard(
            header: const Text('Actions rapides',
                style: TextStyle(fontWeight: FontWeight.w700)),
            child: Column(
              children: [
                ToreCTA(
                    label: 'JE VAIS BIEN',
                    onPressed: _okBusy ? null : () => _checkin('OK'),
                    busy: _okBusy),
                const SizedBox(height: 8),
                ToreCTA(
                  label: 'JE VEUX PARTIR',
                  onPressed: _panicBusy ? null : _confirmPanic,
                  busy: _panicBusy,
                  style: ToreCTAStyle.destructive,
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          ToreCard(
            header: const Text('Historique',
                style: TextStyle(fontWeight: FontWeight.w700)),
            child: historyAsync.when(
              data: (data) {
                final base = data.data.items.take(10).toList(growable: true);
                final optimistic = _optimisticMyLastCheckin;
                if (optimistic != null &&
                    (base.isEmpty ||
                        base.first.createdAt != optimistic.createdAt)) {
                  base.insert(0, optimistic);
                }
                final items = base.take(10).toList(growable: false);
                return Column(
                  children: [
                    if (items.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(12),
                        child: Text('Aucun check-in pour le moment.'),
                      )
                    else
                      ...List.generate(items.length, (index) {
                        final item = items[index];
                        return Column(
                          children: [
                            ToreListRow(
                              title: item.type,
                              subtitle: _relative(item.createdAt),
                              trailing: ToreChip(
                                label: item.type,
                                variant: item.type == 'PANIC'
                                    ? ToreChipVariant.bad
                                    : ToreChipVariant.ok,
                              ),
                            ),
                            if (index < items.length - 1) const ToreDivider(),
                          ],
                        );
                      }),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        data.cacheStatus.isCached
                            ? 'Cache (offline) · Dernière sync: ${_relative(data.cacheStatus.lastSyncAt)}'
                            : 'Dernière sync: ${_relative(data.cacheStatus.lastSyncAt)}',
                      ),
                    ),
                  ],
                );
              },
              loading: () => const Padding(
                  padding: EdgeInsets.all(12),
                  child: CircularProgressIndicator()),
              error: (_, __) =>
                  const Text('Impossible de charger l’historique.'),
            ),
          ),
        ],
      ),
    );
  }
}
