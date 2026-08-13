import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/network/error_mapper.dart';
import '../../../shared/models/event_summary.dart';
import '../../../shared/models/bar.dart';
import '../../../shared/widgets/public_media.dart';
import '../../../ui/app_design_system.dart';
import '../../events/presentation/event_detail_screen.dart';
import 'bars_providers.dart';

class BarDetailScreen extends ConsumerWidget {
  const BarDetailScreen({
    super.key,
    required this.barId,
  });

  final int barId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final events = ref.watch(barEventsProvider(barId));
    final bar = ref.watch(barDetailProvider(barId));
    return Scaffold(
      appBar: AppBar(
        title: Text(bar.when(
          data: (value) => value.name,
          loading: () => 'Bar',
          error: (_, __) => 'Bar',
        )),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(barEventsProvider(barId).future),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(AppSpacing.md),
          children: [
            bar.when(
              loading: () => const ToreCard(child: SizedBox(height: 180)),
              error: (error, _) => ToreCard(
                child: Column(children: [
                  Text(ErrorMapper.message(error)),
                  const SizedBox(height: 10),
                  ToreButton.secondary(
                    label: 'Réessayer',
                    icon: Icons.refresh,
                    onPressed: () => ref.invalidate(barDetailProvider(barId)),
                  ),
                ]),
              ),
              data: (item) => _BarIdentity(bar: item),
            ),
            const SizedBox(height: AppSpacing.md),
            const ToreSectionHeader('Live et à venir'),
            events.when(
              loading: () => const ToreCard(child: SizedBox(height: 100)),
              error: (error, _) => ToreCard(
                child: Column(
                  children: [
                    Text(ErrorMapper.message(error)),
                    const SizedBox(height: 10),
                    ToreButton.secondary(
                      label: 'Réessayer',
                      icon: Icons.refresh,
                      onPressed: () => ref.invalidate(barEventsProvider(barId)),
                    ),
                  ],
                ),
              ),
              data: (result) {
                final visible = result.items
                    .where((event) => event.status != BarEventStatus.ended)
                    .toList(growable: false);
                if (visible.isEmpty) {
                  return const ToreCard(
                    child: Text('Aucune soirée annoncée dans ce bar.'),
                  );
                }
                return Column(
                  children: [
                    if (result.fromCache)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: ToreCard(
                          child: Row(
                            children: [
                              Icon(Icons.cloud_off_outlined),
                              SizedBox(width: 8),
                              Expanded(
                                child:
                                    Text('Événements affichés depuis le cache'),
                              ),
                            ],
                          ),
                        ),
                      ),
                    for (final event in visible)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _BarEventRow(event: event),
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

class _BarIdentity extends StatelessWidget {
  const _BarIdentity({required this.bar});

  final Bar bar;

  @override
  Widget build(BuildContext context) {
    final primary = _brandingColor(bar.primaryColor, const Color(0xFF6E0D18));
    final secondary =
        _brandingColor(bar.secondaryColor, const Color(0xFFF4B400));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Stack(
          alignment: Alignment.bottomLeft,
          children: [
            PublicMedia(
              imageUrl: bar.bannerUrl,
              height: 190,
              icon: Icons.local_bar_outlined,
              fallbackColors: [primary, const Color(0xFF171018), Colors.black],
            ),
            Container(
              margin: const EdgeInsets.all(16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: .76),
                borderRadius: BorderRadius.circular(14),
              ),
              child: Row(children: [
                if (bar.logoUrl != null)
                  ClipOval(
                    child: Image.network(bar.logoUrl!,
                        width: 48,
                        height: 48,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const SizedBox.shrink()),
                  ),
                if (bar.logoUrl != null) const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(bar.name,
                          style: Theme.of(context).textTheme.headlineSmall),
                      if (bar.city.isNotEmpty)
                        Text(bar.city, style: AppTextStyles.muted),
                    ],
                  ),
                ),
              ]),
            ),
          ],
        ),
        if (bar.description != null || bar.practicalInfo != null) ...[
          const SizedBox(height: AppSpacing.sm),
          ToreCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (bar.description != null) Text(bar.description!),
                if (bar.description != null && bar.practicalInfo != null)
                  const SizedBox(height: 10),
                if (bar.practicalInfo != null)
                  Text(bar.practicalInfo!, style: AppTextStyles.muted),
              ],
            ),
          ),
        ],
        if (bar.modules.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: 8,
            children: [
              for (final module in bar.modules)
                Chip(
                  label: Text(module),
                  side: BorderSide(color: secondary.withValues(alpha: .65)),
                )
            ],
          ),
        ],
        const SizedBox(height: AppSpacing.sm),
        ToreButton.secondary(
          label: 'Ouvrir dans la carte',
          icon: Icons.map_outlined,
          onPressed: () => _openMap(context),
        ),
      ],
    );
  }

  Color _brandingColor(String? value, Color fallback) {
    if (value == null) return fallback;
    return Color(int.parse(value.substring(1), radix: 16) | 0xFF000000);
  }

  Future<void> _openMap(BuildContext context) async {
    final explicit = Uri.tryParse(bar.mapUrl ?? '');
    final query = Uri.encodeComponent(
      [bar.name, bar.address, bar.city]
          .whereType<String>()
          .where((v) => v.isNotEmpty)
          .join(', '),
    );
    final target = explicit != null && explicit.hasScheme
        ? explicit
        : Uri.parse('https://www.google.com/maps/search/?api=1&query=$query');
    final launched =
        await launchUrl(target, mode: LaunchMode.externalApplication);
    if (!launched && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Impossible d’ouvrir la carte.')),
      );
    }
  }
}

class _BarEventRow extends StatelessWidget {
  const _BarEventRow({required this.event});

  final EventSummary event;

  @override
  Widget build(BuildContext context) => InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => EventDetailScreen(eventId: event.id),
        )),
        child: ToreCard(
          child: Row(
            children: [
              Icon(event.isLive ? Icons.sensors : Icons.event_outlined,
                  color: event.isLive
                      ? AppColors.accentRed
                      : AppColors.accentGold),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(event.name,
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 4),
                    Text(_dateLabel(event.startAt), style: AppTextStyles.muted),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      );

  String _dateLabel(DateTime value) {
    String two(int item) => item.toString().padLeft(2, '0');
    return '${two(value.day)}/${two(value.month)} · ${two(value.hour)}:${two(value.minute)}';
  }
}
