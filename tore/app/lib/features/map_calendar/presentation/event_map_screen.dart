import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../shared/widgets/service_limited_banner.dart';
import '../../../ui/components/components.dart';
import 'map_calendar_providers.dart';

class EventMapScreen extends ConsumerWidget {
  const EventMapScreen({super.key, required this.eventId});

  final int eventId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncMap = ref.watch(eventMapProvider(eventId));

    return Scaffold(
      appBar: AppBar(title: const Text('Carte')),
      body: asyncMap.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Erreur carte: $e')),
        data: (result) {
          final payload = result.payload;
          final nav = Map<String, dynamic>.from(
              (payload['navettes'] as Map?) ?? const {});
          final lat = (payload['lat'] as num?)?.toDouble();
          final lng = (payload['lng'] as num?)?.toDouble();
          final address = (payload['address'] ?? '').toString();
          final venue = (payload['venueName'] ?? 'Lieu event').toString();
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (result.fromCache)
                const ServiceLimitedBanner(
                    message: 'Mode lecture (cache 24h).'),
              ToreCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(venue, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 6),
                    Text(address.isEmpty ? 'Adresse non renseignée' : address),
                    const SizedBox(height: 8),
                    Wrap(spacing: 8, runSpacing: 8, children: [
                      ToreChip(
                          label: payload['enabled'] == true ? 'ON' : 'OFF',
                          variant: payload['enabled'] == true
                              ? ToreChipVariant.live
                              : ToreChipVariant.closed),
                      if (lat != null && lng != null)
                        ToreChip(
                            label: 'GPS OK', variant: ToreChipVariant.live),
                    ]),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              _NavButton(
                  label: 'Ouvrir Google Maps',
                  onTap: () =>
                      _openGoogle(lat: lat, lng: lng, address: address)),
              _NavButton(
                  label: 'Ouvrir Apple Plans',
                  onTap: () =>
                      _openApple(lat: lat, lng: lng, address: address)),
              _NavButton(
                  label: 'Ouvrir Waze',
                  onTap: () => _openWaze(
                      lat: lat,
                      lng: lng,
                      fallback: payload['wazeLink']?.toString(),
                      address: address)),
              if ((payload['tecLink'] ?? '').toString().isNotEmpty)
                _NavButton(
                    label: 'Ouvrir TEC',
                    onTap: () => _launch(payload['tecLink'].toString())),
              if (nav['enabled'] == true) ...[
                const SizedBox(height: 12),
                ToreCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Navettes',
                          style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 6),
                      Text(
                          'Départ/retour: ${(nav['address'] ?? '—').toString()}'),
                      Text(
                          'Dernier retour: ${(nav['lastReturnTime'] ?? '—').toString()}'),
                      if ((nav['notes'] ?? '').toString().isNotEmpty)
                        Text((nav['notes'] ?? '').toString()),
                    ],
                  ),
                ),
              ],
            ],
          );
        },
      ),
    );
  }

  Future<void> _openGoogle(
      {double? lat, double? lng, required String address}) async {
    final query = (lat != null && lng != null)
        ? '$lat,$lng'
        : Uri.encodeComponent(address);
    await _launch('https://www.google.com/maps/search/?api=1&query=$query');
  }

  Future<void> _openApple(
      {double? lat, double? lng, required String address}) async {
    if (lat != null && lng != null) {
      await _launch('http://maps.apple.com/?ll=$lat,$lng');
      return;
    }
    await _launch('http://maps.apple.com/?q=${Uri.encodeComponent(address)}');
  }

  Future<void> _openWaze(
      {double? lat,
      double? lng,
      String? fallback,
      required String address}) async {
    if (fallback != null && fallback.isNotEmpty) {
      await _launch(fallback);
      return;
    }
    if (lat != null && lng != null) {
      await _launch('https://waze.com/ul?ll=$lat,$lng&navigate=yes');
      return;
    }
    await _launch('https://waze.com/ul?q=${Uri.encodeComponent(address)}');
  }

  Future<void> _launch(String raw) async {
    final uri = Uri.parse(raw);
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: SizedBox(
        width: double.infinity,
        child: FilledButton(onPressed: onTap, child: Text(label)),
      ),
    );
  }
}
