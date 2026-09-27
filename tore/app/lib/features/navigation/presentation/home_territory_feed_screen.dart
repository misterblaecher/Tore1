import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../state.dart';
import '../../../shared/widgets/ui_fallbacks.dart';
import '../../../ui/app_design_system.dart';
import '../../../core/auth/providers.dart';

const _territoryFeedCacheKey = 'territory_feed_cache_v1';
const bool kTrendingEnabled = true;

class HomeTerritoryFeedScreen extends ConsumerStatefulWidget {
  const HomeTerritoryFeedScreen({super.key});

  @override
  ConsumerState<HomeTerritoryFeedScreen> createState() =>
      _HomeTerritoryFeedScreenState();
}

class _HomeTerritoryFeedScreenState
    extends ConsumerState<HomeTerritoryFeedScreen> {
  bool _loading = true;
  String? _error;
  bool _fromCache = false;
  List<_TerritoryEvent> _events = const [];
  List<_ActiveBar> _bars = const [];

  @override
  void initState() {
    super.initState();
    _loadFeed();
  }

  Future<void> _loadFeed() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final barsRaw = await api.bars();
      final bars = barsRaw
          .cast<Map<String, dynamic>>()
          .map((bar) => _ActiveBar(
                id: (bar['id'] as int?) ?? 0,
                name: (bar['name'] ?? 'Bar').toString(),
                distanceLabel: 'à proximité',
              ))
          .toList();

      final events = <_TerritoryEvent>[];
      for (final bar in bars.take(5)) {
        try {
          final eventRaw = await api.events(bar.id);
          for (final item in eventRaw.take(2)) {
            final map = Map<String, dynamic>.from(item as Map);
            events.add(
              _TerritoryEvent(
                id: (map['id'] as int?) ?? 0,
                name: (map['name'] ?? 'Event').toString(),
                distanceLabel: 'à proximité',
                participants: (map['participants_count'] as int?) ?? 0,
                modules: const [
                  Icons.local_bar_outlined,
                  Icons.music_note_outlined,
                  Icons.meeting_room_outlined
                ],
              ),
            );
          }
        } catch (_) {
          // fallback per bar
        }
      }

      final safeEvents = events.isNotEmpty
          ? events
          : [
              const _TerritoryEvent(
                id: 1,
                name: 'Nocturne Liège',
                distanceLabel: 'à proximité',
                participants: 180,
                modules: [Icons.local_bar_outlined, Icons.meeting_room_outlined],
              ),
            ];

      await _saveCache(safeEvents, bars);
      if (!mounted) return;
      setState(() {
        _events = safeEvents;
        _bars = bars;
        _fromCache = false;
      });
    } catch (e) {
      final restored = await _restoreCache();
      if (!mounted) return;
      if (restored != null) {
        setState(() {
          _events = restored.$1;
          _bars = restored.$2;
          _fromCache = true;
          _error = 'Mode hors ligne: dernier feed connu.';
        });
      } else {
        setState(() => _error = 'Impossible de charger le feed territoire.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _saveCache(
      List<_TerritoryEvent> events, List<_ActiveBar> bars) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _territoryFeedCacheKey,
      jsonEncode({
        'events': events
            .map((e) => {
                  'id': e.id,
                  'name': e.name,
                  'distance': e.distanceLabel,
                  'participants': e.participants
                })
            .toList(),
        'bars': bars
            .map((b) =>
                {'id': b.id, 'name': b.name, 'distance': b.distanceLabel})
            .toList(),
      }),
    );
  }

  Future<(List<_TerritoryEvent>, List<_ActiveBar>)?> _restoreCache() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_territoryFeedCacheKey);
    if (raw == null || raw.isEmpty) return null;
    final data = jsonDecode(raw) as Map<String, dynamic>;
    final events = (data['events'] as List<dynamic>? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .map(
          (item) => _TerritoryEvent(
            id: (item['id'] as int?) ?? 0,
            name: (item['name'] ?? 'Event').toString(),
            distanceLabel: (item['distance'] ?? 'à proximité').toString(),
            participants: (item['participants'] as int?) ?? 0,
            modules: const [
              Icons.local_bar_outlined,
              Icons.music_note_outlined
            ],
          ),
        )
        .toList();
    final bars = (data['bars'] as List<dynamic>? ?? const [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .map(
          (item) => _ActiveBar(
            id: (item['id'] as int?) ?? 0,
            name: (item['name'] ?? 'Bar').toString(),
            distanceLabel: (item['distance'] ?? 'à proximité').toString(),
          ),
        )
        .toList();
    return (events, bars);
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authSessionProvider);
    final bottomInset = MediaQuery.of(context).padding.bottom;
    const fabClearance = 132.0;

    return Scaffold(
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: RefreshIndicator(
          onRefresh: _loadFeed,
          child: SafeArea(
            bottom: false,
            child: ListView(
              padding: EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.md,
                AppSpacing.md,
                AppSpacing.md + fabClearance + bottomInset,
              ),
              children: [
                Row(
                  children: [
                    Image.asset(
                      'assets/branding/logo_minimal.png',
                      width: 30,
                      height: 30,
                      errorBuilder: (_, __, ___) =>
                          const Icon(Icons.local_fire_department_outlined),
                    ),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('TORÈ', style: AppTextStyles.massiveTitle),
                          Text('Liège · Territory Hub',
                              style: AppTextStyles.muted),
                        ],
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        const SolarChip(
                            label: 'Territoire Liège',
                            color: AppColors.solarGold),
                        const SizedBox(height: 6),
                        Text(
                          session.isGuest
                              ? 'Exploration invitée'
                              : 'Statut: connecté',
                          style: AppTextStyles.muted,
                        ),
                      ],
                    ),
                  ],
                ),
                if (_fromCache || _error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(_error ?? 'Affichage depuis le cache local.',
                        style: const TextStyle(color: AppColors.warning)),
                  ),
                const SizedBox(height: 16),
                const SolarSectionTitle('Événements actifs'),
                const SizedBox(height: 8),
                if (_loading)
                  const ToreLoadingSkeleton(lines: 4)
                else
                  for (final event in _events)
                    Container(
                      width: double.infinity,
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.all(AppSpacing.sm),
                      decoration: AppColors.solarCardDecoration,
                      child: InkWell(
                        onTap: () {},
                        borderRadius: BorderRadius.circular(12),
                        child: Padding(
                          padding: const EdgeInsets.all(4),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(event.name,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 18)),
                              const SizedBox(height: 6),
                              Text(event.distanceLabel,
                                  style: AppTextStyles.muted),
                              const SizedBox(height: 8),
                              Wrap(spacing: 6, children: [
                                for (final icon in event.modules)
                                  Icon(icon,
                                      size: 16, color: AppColors.solarGold)
                              ]),
                              const SizedBox(height: 8),
                              Text('${event.participants} présents',
                                  style: AppTextStyles.muted),
                            ],
                          ),
                        ),
                      ),
                    ),
                if (!_loading && _events.isEmpty)
                  const ToreEmptyState(
                    title: 'Territoire calme',
                    message: "Aucun événement actif pour l'instant.",
                  ),
                const SizedBox(height: 16),
                const SolarSectionTitle('Bars vivants'),
                const SizedBox(height: 8),
                for (final bar in _bars)
                  Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(AppSpacing.sm),
                    decoration: AppColors.solarCardDecoration,
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(bar.name),
                              Text(bar.distanceLabel,
                                  style: AppTextStyles.muted)
                            ],
                          ),
                        ),
                        const SolarChip(
                            label: 'Actif', color: AppColors.solarRedSoft),
                      ],
                    ),
                  ),
                if (!_loading && _bars.isEmpty)
                  const ToreEmptyState(
                    title: "Aucun bar pour l'instant",
                    message:
                        "Reviens un peu plus tard pour découvrir les bars actifs.",
                  ),
                if (kTrendingEnabled) ...[
                  const SizedBox(height: 12),
                  const SolarSectionTitle('Arènes actives'),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: const [
                      SolarChip(label: 'Arène centrale'),
                      SolarChip(label: 'Territoire étudiant'),
                      SolarChip(label: 'Room active'),
                    ],
                  ),
                ],
                if (session.isGuest) ...[
                  const SizedBox(height: 12),
                  const AuthRequiredNotice(
                      message:
                          'Le check-in, la création d\'event et les outils staff demandent un compte.'),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TerritoryEvent {
  const _TerritoryEvent(
      {required this.id,
      required this.name,
      required this.distanceLabel,
      required this.modules,
      required this.participants});

  final int id;
  final String name;
  final String distanceLabel;
  final List<IconData> modules;
  final int participants;
}

class _ActiveBar {
  const _ActiveBar(
      {required this.id, required this.name, required this.distanceLabel});

  final int id;
  final String name;
  final String distanceLabel;
}
