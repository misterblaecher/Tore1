import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../state.dart';
import '../../../ui/components/components.dart';
import '../../events/presentation/event_hub_screen.dart';
import '../../events/presentation/event_public_screen.dart';
import '../../qr/presentation/code_entry_sheet.dart';
import 'map_calendar_providers.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  CalendarRange _range = CalendarRange.today;

  @override
  Widget build(BuildContext context) {
    final asyncEvents = ref.watch(calendarEventsProvider(_range));
    final hasPublicJoinable = asyncEvents.maybeWhen(
      data: (result) => result.items.any((item) =>
          (item['visibility'] ?? 'PUBLIC').toString().toUpperCase() ==
          'PUBLIC'),
      orElse: () => true,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Calendrier guindaille'),
        actions: [
          if (!hasPublicJoinable)
            TextButton.icon(
              onPressed: () => showCodeEntrySheet(context),
              icon: const Icon(Icons.login_outlined),
              label: const Text('Entrer un code'),
            ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                    label: const Text('Aujourd’hui'),
                    selected: _range == CalendarRange.today,
                    onSelected: (_) =>
                        setState(() => _range = CalendarRange.today)),
                ChoiceChip(
                    label: const Text('Semaine'),
                    selected: _range == CalendarRange.week,
                    onSelected: (_) =>
                        setState(() => _range = CalendarRange.week)),
                ChoiceChip(
                    label: const Text('Mois'),
                    selected: _range == CalendarRange.month,
                    onSelected: (_) =>
                        setState(() => _range = CalendarRange.month)),
              ],
            ),
          ),
          Expanded(
            child: asyncEvents.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, _) => Center(child: Text('Erreur calendrier: $e')),
              data: (result) {
                return ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: result.items.length,
                  itemBuilder: (_, index) {
                    final item = result.items[index];
                    final eventId = int.tryParse('${item['id']}');
                    final start =
                        DateTime.tryParse((item['startAt'] ?? '').toString());
                    final end =
                        DateTime.tryParse((item['endAt'] ?? '').toString());
                    final dateLabel =
                        '${start != null ? TimeOfDay.fromDateTime(start).format(context) : '--'} - ${end != null ? TimeOfDay.fromDateTime(end).format(context) : '--'}';
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: ToreCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text((item['name'] ?? '').toString(),
                                style: const TextStyle(
                                    fontWeight: FontWeight.w700)),
                            const SizedBox(height: 4),
                            Text(
                                '$dateLabel · ${(item['barName'] ?? 'Bar').toString()}'),
                            const SizedBox(height: 8),
                            Wrap(
                              spacing: 8,
                              children: [
                                OutlinedButton(
                                  onPressed: eventId == null
                                      ? null
                                      : () async {
                                          final url = ref
                                              .read(apiProvider)
                                              .getEventIcsUrl(eventId);
                                          await launchUrl(Uri.parse(url),
                                              mode: LaunchMode
                                                  .externalApplication);
                                        },
                                  child: const Text('Ajouter au calendrier'),
                                ),
                                FilledButton(
                                  onPressed: eventId == null
                                      ? null
                                      : () async {
                                          final isPublic =
                                              (item['visibility'] ?? 'PUBLIC')
                                                      .toString()
                                                      .toUpperCase() ==
                                                  'PUBLIC';
                                          if (isPublic) {
                                            try {
                                              final share = await ref
                                                  .read(apiProvider)
                                                  .getEventShareV1(eventId);
                                              final deepLink =
                                                  (share['deeplink'] ?? '')
                                                      .toString();
                                              final webUrl = (share['webUrl'] ??
                                                      share['https_link'] ??
                                                      '')
                                                  .toString();
                                              if (deepLink.isNotEmpty &&
                                                  await canLaunchUrl(
                                                      Uri.parse(deepLink))) {
                                                await launchUrl(
                                                    Uri.parse(deepLink),
                                                    mode: LaunchMode
                                                        .externalApplication);
                                                return;
                                              }
                                              if (webUrl.isNotEmpty) {
                                                await launchUrl(
                                                    Uri.parse(webUrl),
                                                    mode: LaunchMode
                                                        .externalApplication);
                                                return;
                                              }
                                            } catch (_) {
                                              // fallback in-app join below
                                            }
                                            if (!context.mounted) return;
                                            Navigator.of(context).push(
                                                MaterialPageRoute(
                                                    builder: (_) =>
                                                        EventPublicScreen(
                                                            eventId: eventId)));
                                            return;
                                          }
                                          if (!context.mounted) return;
                                          Navigator.of(context).push(
                                              MaterialPageRoute(
                                                  builder: (_) =>
                                                      EventHubScreen(
                                                          eventId: eventId,
                                                          eventName: (item[
                                                                      'name'] ??
                                                                  '')
                                                              .toString())));
                                        },
                                  child: const Text('Ouvrir'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
