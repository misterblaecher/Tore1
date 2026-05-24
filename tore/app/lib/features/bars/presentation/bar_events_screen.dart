import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/theme/theme.dart';
import 'package:tore/ui/components/components.dart';

import '../../../core/app_context/app_context.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/models/event_summary.dart';
import '../../events/presentation/event_hub_screen.dart';
import 'bars_providers.dart';

class BarEventsScreen extends ConsumerWidget {
  const BarEventsScreen(
      {super.key, required this.barId, required this.barName});

  final int barId;
  final String barName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final eventsAsync = ref.watch(barEventsProvider(barId));

    return Scaffold(
      appBar: AppBar(title: Text(barName)),
      body: RefreshIndicator(
        onRefresh: () async => ref.refresh(barEventsProvider(barId).future),
        child: eventsAsync.when(
          loading: () => const _LoadingState(),
          error: (error, _) => _ErrorState(
            message: ErrorMapper.message(error),
            onRetry: () => ref.invalidate(barEventsProvider(barId)),
          ),
          data: (events) {
            final grouped = _groupEvents(events);
            final hasItems = grouped.live.isNotEmpty ||
                grouped.today.isNotEmpty ||
                grouped.upcoming.isNotEmpty;
            if (!hasItems) {
              return const _EmptyState();
            }
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(ToreSpace.s4),
              children: [
                if (grouped.live.isNotEmpty)
                  _EventSection(
                    title: 'LIVE',
                    events: grouped.live,
                    onTap: (event) =>
                        _openEvent(context: context, ref: ref, event: event),
                  ),
                if (grouped.today.isNotEmpty)
                  _EventSection(
                    title: 'TODAY',
                    events: grouped.today,
                    onTap: (event) =>
                        _openEvent(context: context, ref: ref, event: event),
                  ),
                if (grouped.upcoming.isNotEmpty)
                  _EventSection(
                    title: 'UPCOMING',
                    events: grouped.upcoming,
                    onTap: (event) =>
                        _openEvent(context: context, ref: ref, event: event),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }

  void _openEvent({
    required BuildContext context,
    required WidgetRef ref,
    required EventSummary event,
  }) {
    ref
        .read(appContextProvider.notifier)
        .setBar(barId: barId, barName: barName);
    ref.read(appContextProvider.notifier).enterEvent(
          eventId: event.id,
          eventName: event.name,
          activeEventModules: event.modulesOn,
        );

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) =>
            EventHubScreen(eventId: event.id, eventName: event.name),
      ),
    );
  }
}

class _GroupedEvents {
  const _GroupedEvents(
      {required this.live, required this.today, required this.upcoming});

  final List<EventSummary> live;
  final List<EventSummary> today;
  final List<EventSummary> upcoming;
}

_GroupedEvents _groupEvents(List<EventSummary> events) {
  final live = <EventSummary>[];
  final today = <EventSummary>[];
  final upcoming = <EventSummary>[];

  for (final event in events) {
    if (event.isLive) {
      live.add(event);
      continue;
    }
    if (event.isToday()) {
      today.add(event);
      continue;
    }
    if (event.startAt.isAfter(DateTime.now())) {
      upcoming.add(event);
    }
  }

  return _GroupedEvents(live: live, today: today, upcoming: upcoming);
}

class _EventSection extends StatelessWidget {
  const _EventSection(
      {required this.title, required this.events, required this.onTap});

  final String title;
  final List<EventSummary> events;
  final ValueChanged<EventSummary> onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: ToreSpace.s4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: ToreSpace.s2),
            child: Text(title, style: ToreType.h3),
          ),
          ...events.map(
            (event) => Padding(
              padding: const EdgeInsets.only(bottom: ToreSpace.s2),
              child: _EventCard(
                  event: event, onTap: () => onTap(event), section: title),
            ),
          ),
        ],
      ),
    );
  }
}

class _EventCard extends StatelessWidget {
  const _EventCard(
      {required this.event, required this.onTap, required this.section});

  final EventSummary event;
  final VoidCallback onTap;
  final String section;

  @override
  Widget build(BuildContext context) {
    final start = TimeOfDay.fromDateTime(event.startAt);
    final end = TimeOfDay.fromDateTime(event.endAt);
    final timeLabel = '${start.format(context)} - ${end.format(context)}';
    final subtitle = [event.venue, event.shortName]
        .whereType<String>()
        .where((value) => value.trim().isNotEmpty)
        .toSet()
        .join(' · ');

    return InkWell(
      borderRadius: BorderRadius.circular(ToreRadii.md),
      onTap: onTap,
      child: ToreCard(
        child: Column(
          children: [
            ToreListRow(
              title: event.name,
              subtitle: subtitle.isEmpty ? null : subtitle,
              trailing: const Icon(Icons.chevron_right),
            ),
            const ToreDivider(),
            const SizedBox(height: ToreSpace.s2),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: ToreSpace.s4),
              child: Row(
                children: [
                  Text(timeLabel, style: ToreType.monoMetric),
                  const Spacer(),
                  ToreChip(label: section, variant: _chipVariant(section)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  ToreChipVariant _chipVariant(String value) {
    switch (value) {
      case 'LIVE':
        return ToreChipVariant.live;
      case 'TODAY':
        return ToreChipVariant.ok;
      case 'UPCOMING':
        return ToreChipVariant.info;
      default:
        return ToreChipVariant.info;
    }
  }
}

class _LoadingState extends StatelessWidget {
  const _LoadingState();

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(ToreSpace.s4),
      itemCount: 4,
      itemBuilder: (_, __) => const Padding(
        padding: EdgeInsets.only(bottom: ToreSpace.s3),
        child: ToreCard(
          child: SizedBox(height: 72),
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 120),
        Center(
            child: Text('Aucun event',
                style: Theme.of(context).textTheme.titleMedium)),
        const SizedBox(height: 8),
        Center(
          child: TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Back to bars'),
          ),
        ),
      ],
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        const SizedBox(height: 120),
        const Center(child: Text('Impossible de charger les events.')),
        const SizedBox(height: 8),
        Center(
          child: Text(
            message,
            style: ToreType.meta.copyWith(color: ToreSemantic.textMuted),
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 12),
        Center(
          child: FilledButton(onPressed: onRetry, child: const Text('Retry')),
        ),
      ],
    );
  }
}
