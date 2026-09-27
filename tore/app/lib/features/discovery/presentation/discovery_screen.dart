import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/error_mapper.dart';
import '../../../ui/app_design_system.dart';
import '../../../shared/widgets/public_media.dart';
import '../../bars/presentation/bars_screen.dart';
import '../../community/presentation/community_screen.dart';
import '../../events/presentation/event_detail_screen.dart';
import '../domain/discovery_models.dart';
import 'discovery_providers.dart';

class DiscoveryScreen extends ConsumerStatefulWidget {
  const DiscoveryScreen({super.key, this.compactHome = false});

  final bool compactHome;

  @override
  ConsumerState<DiscoveryScreen> createState() => _DiscoveryScreenState();
}

class _DiscoveryScreenState extends ConsumerState<DiscoveryScreen> {
  late final TextEditingController _searchController;
  Timer? _debounce;
  bool _locating = false;

  Future<void> _toggleNearby(bool selected) async {
    if (!selected) {
      final current = ref.read(discoveryQueryProvider);
      ref.read(discoveryQueryProvider.notifier).state =
          current.copyWith(clearNearby: true);
      return;
    }
    setState(() => _locating = true);
    try {
      final coords = await ref.read(nearbyLocationServiceProvider).locate();
      if (!mounted) return;
      if (coords == null) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
              'Localisation indisponible. Toutes les soirées restent affichées.'),
        ));
        return;
      }
      final current = ref.read(discoveryQueryProvider);
      ref.read(discoveryQueryProvider.notifier).state = current.copyWith(
        clearCity: true,
        lat: coords.lat,
        lng: coords.lng,
        radius: 20,
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
              'Position introuvable. Toutes les soirées restent affichées.'),
        ));
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(
      text: ref.read(discoveryQueryProvider).search,
    );
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _updateSearch(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (!mounted) return;
      final current = ref.read(discoveryQueryProvider);
      ref.read(discoveryQueryProvider.notifier).state =
          current.copyWith(search: value);
    });
  }

  @override
  Widget build(BuildContext context) {
    final query = ref.watch(discoveryQueryProvider);
    final events = ref.watch(discoveryEventsProvider(query));

    return Scaffold(
      appBar: widget.compactHome
          ? null
          : AppBar(title: const Text('Soirées')),
      body: RefreshIndicator(
        onRefresh: () async =>
            ref.refresh(discoveryEventsProvider(query).future),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            if (widget.compactHome) ...[
              Text('Découvre ta soirée',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 6),
              const Text(
                'Live, ce soir et à venir — le scan reste un raccourci.',
                style: AppTextStyles.muted,
              ),
              const SizedBox(height: AppSpacing.md),
            ],
            TextField(
              controller: _searchController,
              onChanged: _updateSearch,
              textInputAction: TextInputAction.search,
              decoration: const InputDecoration(
                hintText: 'Soirée, bar, structure ou lieu',
                prefixIcon: Icon(Icons.search),
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: FilterChip(
                      avatar: const Icon(Icons.near_me_outlined, size: 18),
                      label: Text(_locating
                          ? 'Localisation…'
                          : 'Autour de moi · 20 km'),
                      selected: query.isNearby,
                      onSelected: _locating ? null : _toggleNearby,
                    ),
                  ),
                  for (final status in DiscoveryStatus.values)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Text(status.label),
                        selected: query.status == status,
                        onSelected: (_) {
                          ref.read(discoveryQueryProvider.notifier).state =
                              query.copyWith(status: status);
                        },
                      ),
                    ),
                ],
              ),
            ),
            if (widget.compactHome) ...[
              const SizedBox(height: AppSpacing.md),
              Row(
                children: [
                  Expanded(
                    child: _HomeShortcut(
                      icon: Icons.local_bar_outlined,
                      label: 'Bars',
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const BarsScreen()),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: _HomeShortcut(
                      icon: Icons.groups_outlined,
                      label: 'Structures',
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(
                            builder: (_) => const CommunityScreen()),
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: AppSpacing.md),
            events.when(
              loading: () => const _DiscoveryLoading(),
              error: (error, _) => _DiscoveryError(
                message: ErrorMapper.message(error),
                onRetry: () => ref.invalidate(discoveryEventsProvider(query)),
              ),
              data: (result) {
                if (result.events.isEmpty) {
                  return const _DiscoveryEmpty();
                }
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (result.fromCache)
                      _CacheNotice(lastSyncAt: result.lastSyncAt),
                    if (result.fromCache) const SizedBox(height: AppSpacing.sm),
                    for (final event in result.events)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: DiscoveryEventCard(event: event),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _HomeShortcut extends StatelessWidget {
  const _HomeShortcut({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: ToreCard(
          child: SizedBox(
            height: 64,
            child: Row(
              children: [
                Icon(icon, color: AppColors.accentGold),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    label,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                const Icon(Icons.chevron_right),
              ],
            ),
          ),
        ),
      );
}

class DiscoveryEventCard extends StatelessWidget {
  const DiscoveryEventCard({super.key, required this.event});

  final DiscoveryEvent event;

  @override
  Widget build(BuildContext context) {
    final location = [event.barName, event.venue, event.city]
        .whereType<String>()
        .where((value) => value.trim().isNotEmpty)
        .toSet()
        .join(' · ');
    return Semantics(
      button: true,
      label: 'Voir le détail de ${event.name}',
      child: InkWell(
        key: ValueKey('event-card-${event.id}'),
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => EventDetailScreen(eventId: event.id),
          ),
        ),
        child: ToreCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PublicMedia(
                imageUrl: event.imageUrl,
                height: 140,
                borderRadius: const BorderRadius.all(Radius.circular(12)),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppColors.solarRedSoft,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(Icons.celebration_outlined,
                        color: AppColors.accentGold),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(event.name,
                                  style:
                                      Theme.of(context).textTheme.titleLarge),
                            ),
                            if (event.isLive) const Chip(label: Text('LIVE')),
                          ],
                        ),
                        if (event.hostName != null)
                          Text(event.hostName!, style: AppTextStyles.muted),
                      ],
                    ),
                  ),
                ],
              ),
              if (event.shortDescription != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  event.shortDescription!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppTextStyles.muted,
                ),
              ],
              const SizedBox(height: AppSpacing.sm),
              _MetadataLine(
                icon: Icons.schedule,
                text: _dateLabel(event.startsAt, event.endsAt),
              ),
              if (location.isNotEmpty)
                _MetadataLine(icon: Icons.place_outlined, text: location),
              if (event.distanceKm != null)
                _MetadataLine(
                  icon: Icons.near_me_outlined,
                  text: '${event.distanceKm!.toStringAsFixed(1)} km',
                ),
              _MetadataLine(
                icon: Icons.confirmation_number_outlined,
                text: event.isFree
                    ? 'Entrée gratuite'
                    : '${(event.entryPriceCents / 100).toStringAsFixed(2)} €',
              ),
              const SizedBox(height: 4),
              const Align(
                alignment: Alignment.centerRight,
                child: Text('Voir le détail  →',
                    style: TextStyle(
                        color: AppColors.accentGold,
                        fontWeight: FontWeight.w700)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static String _dateLabel(DateTime start, DateTime end) {
    String two(int value) => value.toString().padLeft(2, '0');
    return '${two(start.day)}/${two(start.month)} · ${two(start.hour)}:${two(start.minute)}–${two(end.hour)}:${two(end.minute)}';
  }
}

class _MetadataLine extends StatelessWidget {
  const _MetadataLine({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Row(
          children: [
            Icon(icon, size: 18, color: Colors.white70),
            const SizedBox(width: 8),
            Expanded(child: Text(text, style: AppTextStyles.muted)),
          ],
        ),
      );
}

class _CacheNotice extends StatelessWidget {
  const _CacheNotice({required this.lastSyncAt});

  final DateTime lastSyncAt;

  @override
  Widget build(BuildContext context) {
    final local = lastSyncAt.toLocal();
    final time =
        '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_outlined, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text('Données en cache · synchronisées à $time')),
        ],
      ),
    );
  }
}

class _DiscoveryLoading extends StatelessWidget {
  const _DiscoveryLoading();

  @override
  Widget build(BuildContext context) => const Column(
        children: [
          ToreCard(child: SizedBox(height: 120)),
          SizedBox(height: AppSpacing.sm),
          ToreCard(child: SizedBox(height: 120)),
        ],
      );
}

class _DiscoveryEmpty extends StatelessWidget {
  const _DiscoveryEmpty();

  @override
  Widget build(BuildContext context) => const ToreCard(
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: 24),
          child: Column(
            children: [
              Icon(Icons.event_busy_outlined, size: 40),
              SizedBox(height: 10),
              Text('Aucune soirée ne correspond à ces filtres.'),
            ],
          ),
        ),
      );
}

class _DiscoveryError extends StatelessWidget {
  const _DiscoveryError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => ToreCard(
        child: Column(
          children: [
            const Icon(Icons.wifi_off_outlined, size: 40),
            const SizedBox(height: 10),
            const Text('Impossible de charger les soirées.'),
            const SizedBox(height: 6),
            Text(message, style: AppTextStyles.muted),
            const SizedBox(height: 12),
            ToreButton.secondary(
              label: 'Réessayer',
              icon: Icons.refresh,
              onPressed: onRetry,
            ),
          ],
        ),
      );
}
