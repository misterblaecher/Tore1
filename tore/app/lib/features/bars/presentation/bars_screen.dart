import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/theme/theme.dart';
import 'package:tore/ui/components/components.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/models/bar.dart';
import 'bars_providers.dart';

class BarsScreen extends ConsumerWidget {
  const BarsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final barsAsync = ref.watch(barsFutureProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Bars'),
        actions: [
          IconButton(
            tooltip: 'Search',
            onPressed: () {},
            icon: const Icon(Icons.search),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(barsFutureProvider.future),
        child: barsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => ListView(
            children: [
              const SizedBox(height: 80),
              const Center(child: Text('Impossible de charger les bars.')),
              const SizedBox(height: 8),
              Center(
                child: Text(
                  ErrorMapper.message(error),
                  style: ToreType.meta.copyWith(color: ToreSemantic.textMuted),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
          ),
          data: (bars) {
            if (bars.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Center(child: Text('Aucun bar disponible.')),
                ],
              );
            }

            return ListView.separated(
              padding: const EdgeInsets.all(ToreSpace.s4),
              itemCount: bars.length,
              separatorBuilder: (_, __) => const SizedBox(height: ToreSpace.s3),
              itemBuilder: (context, index) =>
                  _BarCompactCard(bar: bars[index]),
            );
          },
        ),
      ),
    );
  }
}

class _BarCompactCard extends ConsumerWidget {
  const _BarCompactCard({required this.bar});

  final Bar bar;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final status = bar.status?.toUpperCase();
    final metadata = [bar.district, bar.style]
        .whereType<String>()
        .where((value) => value.trim().isNotEmpty)
        .join(' · ');
    final ticker = bar.tickerLine ?? bar.lastEvent;

    return InkWell(
      borderRadius: BorderRadius.circular(ToreRadii.md),
      onTap: () {
        ref.read(appContextProvider.notifier).setBar(
              barId: bar.id,
              barName: bar.name,
            );
        Navigator.of(context)
            .pushNamed('/bars/${bar.id}/events', arguments: bar.name);
      },
      child: ToreCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ToreListRow(
              title: bar.name,
              subtitle: metadata.isEmpty
                  ? (bar.city.isEmpty ? null : bar.city)
                  : metadata,
              trailing: const Icon(Icons.chevron_right),
            ),
            const ToreDivider(),
            const SizedBox(height: ToreSpace.s2),
            Row(
              children: [
                if (bar.distanceLabel != null)
                  Padding(
                    padding: const EdgeInsets.only(right: ToreSpace.s2),
                    child: Text(bar.distanceLabel!, style: ToreType.monoMetric),
                  ),
                if (status != null)
                  ToreChip(
                    label: status,
                    variant: _variantForStatus(status),
                  ),
              ],
            ),
            if (ticker != null) ...[
              const SizedBox(height: ToreSpace.s2),
              Text(
                ticker,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style:
                    ToreType.meta.copyWith(color: ToreSemantic.textSecondary),
              ),
            ],
          ],
        ),
      ),
    );
  }

  ToreChipVariant _variantForStatus(String status) {
    switch (status) {
      case 'OPEN':
        return ToreChipVariant.ok;
      case 'LIVE':
        return ToreChipVariant.live;
      case 'CLOSED':
        return ToreChipVariant.closed;
      default:
        return ToreChipVariant.info;
    }
  }
}
