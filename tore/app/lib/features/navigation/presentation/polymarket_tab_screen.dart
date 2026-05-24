import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/providers.dart';
import '../../../core/network/error_mapper.dart';
import '../../../shared/widgets/require_auth_sheet.dart';
import '../../../shared/widgets/ui_fallbacks.dart';
import '../../../ui/app_design_system.dart';
import '../../polymarket/polymarket_models.dart';
import '../../../state.dart';

class PolymarketTabScreen extends ConsumerStatefulWidget {
  const PolymarketTabScreen({super.key});

  @override
  ConsumerState<PolymarketTabScreen> createState() =>
      _PolymarketTabScreenState();
}

class _PolymarketTabScreenState extends ConsumerState<PolymarketTabScreen> {
  bool _loading = true;
  bool _hasError = false;
  String? _error;
  List<MarketLite> _markets = const [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _hasError = false;
      _error = null;
    });

    try {
      final response = await ref
          .read(apiProvider)
          .fetchPolymarketMarkets(scope: 'global', status: 'all', type: 'all');
      if (!mounted) return;
      setState(() {
        _markets = response.items;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _hasError = true;
        _error = ErrorMapper.message(e);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authSessionProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Polymarket')),
      backgroundColor: AppColors.backgroundPrimary,
      body: SolarBackground(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              if (_loading) ...[
                const ToreSectionHeader('Chargement des marchés'),
                const ToreLoadingSkeleton(lines: 8),
              ] else if (_hasError)
                ToreErrorState(
                    message: _error ?? 'Impossible de charger les marchés.',
                    onRetry: _load)
              else if (_markets.isEmpty)
                const ToreEmptyState(
                  title: 'Aucun marché actif',
                  message:
                      'Les marchés seront affichés ici dès leur ouverture.',
                )
              else ...[
                _section(
                    'En feu',
                    _markets
                        .where((m) => m.volume > 1000 || m.poolTickets > 1000)
                        .toList(),
                    session.isGuest),
                _section(
                    'Live',
                    _markets
                        .where((m) => m.status.toLowerCase() == 'live')
                        .toList(),
                    session.isGuest),
                _section(
                    'Résolus',
                    _markets
                        .where((m) => m.status.toLowerCase() == 'resolved')
                        .toList(),
                    session.isGuest),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _section(String title, List<MarketLite> items, bool isGuest) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ToreSectionHeader(title),
        if (items.isEmpty)
          const Padding(
            padding: EdgeInsets.only(bottom: AppSpacing.md),
            child: Text('Aucun élément dans cette section.',
                style: AppTextStyles.muted),
          )
        else
          ...items.map((market) => Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: ToreCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                              child: Text(market.question,
                                  style: const TextStyle(
                                      fontWeight: FontWeight.w700))),
                          if (market.volume > 1200)
                            const AppChip(
                                label: 'CHAUD', color: AppColors.accentAmber),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                          'Oui ${(market.yesPct * 100).toStringAsFixed(0)}% • Non ${(market.noPct * 100).toStringAsFixed(0)}%'),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                          'Participants ${market.poolTickets} • Volume ${market.volume}',
                          style: AppTextStyles.muted),
                      const SizedBox(height: AppSpacing.sm),
                      ToreButton.primary(
                        label: isGuest
                            ? 'Connecte-toi pour continuer'
                            : 'Voir le marché',
                        icon:
                            isGuest ? Icons.lock_outline : Icons.arrow_forward,
                        onPressed: () {
                          if (isGuest) {
                            RequireAuthSheet.show(context,
                                message:
                                    'La prise de position nécessite une connexion.');
                            return;
                          }
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text(
                                    'Lecture ouverte: marché consultable depuis cet écran.')),
                          );
                        },
                      ),
                    ],
                  ),
                ),
              )),
        const SizedBox(height: AppSpacing.md),
      ],
    );
  }
}
