import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/auth/providers.dart';
import '../../../core/network/api_exception.dart';
import '../../../core/network/error_mapper.dart';
import '../../../core/network/network_state_provider.dart';
import '../../../shared/widgets/require_auth_sheet.dart';
import '../../../shared/widgets/public_media.dart';
import '../../../ui/app_design_system.dart';
import '../../bars/presentation/bar_detail_screen.dart';
import '../data/event_detail_repository.dart';
import '../domain/event_public_view.dart';
import 'event_detail_providers.dart';
import 'event_hub_screen.dart';

class EventDetailScreen extends ConsumerStatefulWidget {
  const EventDetailScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<EventDetailScreen> createState() => _EventDetailScreenState();
}

class _EventDetailScreenState extends ConsumerState<EventDetailScreen> {
  bool _joining = false;
  bool _joined = false;
  String? _joinError;
  String? _joinIntentKey;

  String get _idempotencyKey => _joinIntentKey ??=
      'event-join-${widget.eventId}-${DateTime.now().microsecondsSinceEpoch}';

  Future<void> _join(EventPublicView event) async {
    if (_joining || _joined) return;
    final session = ref.read(authSessionProvider);
    if (!session.isAuthed && !session.isGuest) {
      await RequireAuthSheet.show(context,
          message: 'Connecte-toi ou continue en invité pour rejoindre.');
      return;
    }
    if (ref.read(networkStatusProvider) != NetworkState.online) {
      setState(() => _joinError =
          'Rejoindre une soirée nécessite une connexion. Aucune action n’a été enregistrée.');
      return;
    }
    if (!event.canJoin) {
      setState(() => _joinError = 'Les inscriptions sont fermées.');
      return;
    }

    setState(() {
      _joining = true;
      _joinError = null;
    });
    try {
      var payload = await ref.read(eventDetailRepositoryProvider).joinEvent(
            eventId: widget.eventId,
            idempotencyKey: _idempotencyKey,
          );
      if (payload['charter_required'] == true) {
        final version = payload['charter_version']?.toString();
        if (version == null || !await _acceptCharter(version)) return;
        payload = await ref.read(eventDetailRepositoryProvider).joinEvent(
              eventId: widget.eventId,
              idempotencyKey: _idempotencyKey,
              acceptedCharterVersion: version,
            );
      }
      final eventPayload = Map<String, dynamic>.from(
          (payload['event'] as Map?) ?? const <String, dynamic>{});
      final modulesRaw = payload['modulesOn'];
      final modules = modulesRaw is Map
          ? modulesRaw.map(
              (key, value) => MapEntry(key.toString(), value == true),
            )
          : {for (final module in event.modulesOn) module: true};
      final eventName = (eventPayload['name'] ?? event.name).toString().trim();
      ref.read(appContextProvider.notifier).enterEvent(
            eventId: widget.eventId,
            eventName: eventName,
            activeEventModules: modules,
          );
      if (!mounted) return;
      setState(() => _joined = true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Soirée rejointe.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _joinError = _joinMessage(error));
    } finally {
      if (mounted) setState(() => _joining = false);
    }
  }

  Future<bool> _acceptCharter(String version) async {
    try {
      final charter = await ref
          .read(eventDetailRepositoryProvider)
          .fetchCharter(widget.eventId);
      if (!mounted) return false;
      return await showDialog<bool>(
            context: context,
            builder: (_) => AlertDialog(
              title: const Text('Conditions de la soirée'),
              content: SingleChildScrollView(
                child: Text((charter['text'] ?? '').toString()),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('Refuser'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('Accepter'),
                ),
              ],
            ),
          ) ??
          false;
    } catch (error) {
      if (mounted) setState(() => _joinError = ErrorMapper.message(error));
      return false;
    }
  }

  String _joinMessage(Object error) {
    final reason = _reason(error);
    switch (reason) {
      case 'closed':
      case 'expired':
        return 'Cette soirée est terminée.';
      case 'full':
      case 'event_full':
        return 'Cette soirée est complète.';
      case 'forbidden':
      case 'join_forbidden':
        return 'Tu ne peux pas rejoindre cette soirée.';
      case 'already_joined':
        return 'Tu as déjà rejoint cette soirée.';
      case 'frozen':
        return 'Les inscriptions sont temporairement suspendues.';
      default:
        return ErrorMapper.message(error);
    }
  }

  String? _reason(Object error) {
    dynamic details;
    if (error is DioException) {
      if (error.error is ApiException) {
        details = (error.error as ApiException).details;
      } else {
        details = error.response?.data;
      }
    } else if (error is ApiException) {
      details = error.details;
    }
    if (details is Map) {
      final detail = details['detail'];
      if (detail is Map) return detail['reason']?.toString();
      return details['reason']?.toString();
    }
    return null;
  }

  void _openHub(EventPublicView event) {
    ref.read(appContextProvider.notifier).enterEvent(
      eventId: event.id,
      eventName: event.name,
      activeEventModules: {
        for (final module in event.modulesOn) module: true,
      },
    );
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => EventHubScreen(eventId: event.id, eventName: event.name),
    ));
  }

  Future<void> _share(EventPublicView event) async {
    final url = event.openUrl.isNotEmpty ? event.openUrl : event.webUrl;
    await Share.share(
      url.isEmpty ? event.name : '${event.name}\n$url',
      subject: event.name,
    );
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(eventDetailProvider(widget.eventId));
    return Scaffold(
      appBar: AppBar(title: const Text('Détail de la soirée')),
      body: detail.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _ErrorState(
          message: ErrorMapper.message(error),
          onRetry: () => ref.invalidate(eventDetailProvider(widget.eventId)),
        ),
        data: (result) => _EventDetailBody(
          result: result,
          joining: _joining,
          joined: _joined,
          joinError: _joinError,
          onJoin: () => _join(result.event),
          onOpenHub: () => _openHub(result.event),
          onShare: () => _share(result.event),
        ),
      ),
    );
  }
}

class _EventDetailBody extends StatelessWidget {
  const _EventDetailBody({
    required this.result,
    required this.joining,
    required this.joined,
    required this.joinError,
    required this.onJoin,
    required this.onOpenHub,
    required this.onShare,
  });

  final EventDetailResult result;
  final bool joining;
  final bool joined;
  final String? joinError;
  final VoidCallback onJoin;
  final VoidCallback onOpenHub;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) {
    final event = result.event;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.md),
      children: [
        SizedBox(
          height: 220,
          child: Stack(
            children: [
              Positioned.fill(
                child: PublicMedia(imageUrl: event.imageUrl, height: 220),
              ),
              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    gradient: const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Colors.transparent, Color(0xDD050506)],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Text(
                        [event.eventType, event.eventState.toUpperCase()]
                            .whereType<String>()
                            .join(' · '),
                        style: const TextStyle(
                            color: AppColors.accentGold,
                            fontWeight: FontWeight.w800)),
                    const SizedBox(height: 6),
                    Text(event.name,
                        style: Theme.of(context).textTheme.headlineMedium),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (result.fromCache) ...[
          const SizedBox(height: AppSpacing.sm),
          const _InfoBanner(
            icon: Icons.cloud_off_outlined,
            text:
                'Détail affiché depuis le cache. Le join reste indisponible hors ligne.',
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        ToreCard(
          child: Column(
            children: [
              _DetailRow(
                icon: Icons.schedule,
                label: 'Horaire',
                value: _dateLabel(event.startAt, event.endAt),
              ),
              _DetailRow(
                icon: Icons.place_outlined,
                label: 'Lieu',
                value: [event.venueName, event.city]
                    .followedBy([event.address])
                    .whereType<String>()
                    .where((value) => value.isNotEmpty)
                    .toSet()
                    .join(' · '),
              ),
              _DetailRow(
                icon: Icons.groups_outlined,
                label: 'Organisateur',
                value: event.hostName ?? 'Non renseigné',
              ),
              _DetailRow(
                icon: Icons.confirmation_number_outlined,
                label: 'Conditions',
                value: event.isFree
                    ? 'Entrée gratuite'
                    : '${(event.entryPriceCents / 100).toStringAsFixed(2)} ${event.currency}',
              ),
              _DetailRow(
                icon: Icons.policy_outlined,
                label: 'Accès',
                value: event.charterRequired
                    ? '${_accessLabel(event.accessType)} · charte à accepter'
                    : _accessLabel(event.accessType),
              ),
              if (event.capacity != null)
                _DetailRow(
                  icon: Icons.people_outline,
                  label: 'Capacité',
                  value: '${event.capacity} personnes',
                ),
            ],
          ),
        ),
        if (event.barId != null) ...[
          const SizedBox(height: AppSpacing.sm),
          ToreButton.secondary(
            label: 'Voir la page du bar',
            icon: Icons.local_bar_outlined,
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => BarDetailScreen(barId: event.barId!),
            )),
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        const ToreSectionHeader('À propos'),
        ToreCard(
          child: Text(
            event.description ??
                'Aucune description publique n’a été renseignée.',
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        const ToreSectionHeader('Modules actifs'),
        ToreCard(
          child: event.modulesOn.isEmpty
              ? const Text('Aucun module supplémentaire annoncé.')
              : Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final module in event.modulesOn)
                      Chip(label: Text(_moduleLabel(module))),
                  ],
                ),
        ),
        if (joinError != null) ...[
          const SizedBox(height: AppSpacing.sm),
          _InfoBanner(icon: Icons.error_outline, text: joinError!),
        ],
        const SizedBox(height: AppSpacing.md),
        ToreButton.primary(
          label: joined
              ? 'Ouvrir la soirée'
              : joining
                  ? 'Connexion à la soirée…'
                  : 'Rejoindre la soirée',
          icon: joined ? Icons.arrow_forward : Icons.login,
          loading: joining,
          onPressed: joining ? null : (joined ? onOpenHub : onJoin),
        ),
        const SizedBox(height: AppSpacing.sm),
        ToreButton.secondary(
          label: 'Partager',
          icon: Icons.share_outlined,
          onPressed: onShare,
        ),
        const SizedBox(height: 8),
        const Text(
          'Le QR est un raccourci contextuel. Tu peux découvrir et rejoindre cette soirée sans scanner.',
          textAlign: TextAlign.center,
          style: AppTextStyles.muted,
        ),
      ],
    );
  }

  static String _dateLabel(DateTime? start, DateTime? end) {
    if (start == null || end == null) return 'Non renseigné';
    String two(int value) => value.toString().padLeft(2, '0');
    return '${two(start.day)}/${two(start.month)} · ${two(start.hour)}:${two(start.minute)}–${two(end.hour)}:${two(end.minute)}';
  }

  static String _moduleLabel(String module) {
    const labels = {
      'menu': 'Menu',
      'wallet': 'Credits',
      'ticker': 'Live',
      'entry': 'Entrée',
      'checkin': 'Check-in',
      'battles': 'Battles',
      'hunt': 'Hunts',
      'report': 'Infos',
      'polymarket': 'Rooms',
      'polymarket_event': 'Rooms',
      'classement': 'Classement',
      'music_vote': 'Musique',
      'broadcast': 'Annonces',
      'map': 'Carte',
    };
    return labels[module] ?? module;
  }

  static String _accessLabel(String value) {
    const labels = {
      'OPEN': 'Accès libre',
      'TICKET': 'Billet requis',
      'INVITE': 'Sur invitation',
      'APPROVAL': 'Sur demande',
    };
    return labels[value.toUpperCase()] ?? 'Accès public';
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, size: 22, color: AppColors.accentGold),
            const SizedBox(width: 12),
            SizedBox(width: 90, child: Text(label, style: AppTextStyles.muted)),
            Expanded(child: Text(value.isEmpty ? 'Non renseigné' : value)),
          ],
        ),
      );
}

class _InfoBanner extends StatelessWidget {
  const _InfoBanner({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.warning.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Expanded(child: Text(text)),
          ],
        ),
      );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.event_busy_outlined, size: 44),
              const SizedBox(height: 12),
              Text(message, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              ToreButton.secondary(
                label: 'Réessayer',
                icon: Icons.refresh,
                onPressed: onRetry,
              ),
            ],
          ),
        ),
      );
}
