import 'package:flutter/material.dart';

import '../../../models/backend_models.dart';
import '../../../routing/app_routes.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';
import '../../widgets/section_header.dart';
import 'bars_preview.dart';
import 'nearby_events_preview.dart';
import 'quick_actions.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    super.key,
    required this.activeAction,
    required this.onOpenAction,
    required this.onCloseAction,
    required this.eventName,
    required this.barName,
    required this.onOpenEventHub,
    required this.onOpenEvents,
    required this.onOpenBars,
    required this.onOpenExternalUrl,
  });

  final HomeQuickAction? activeAction;
  final ValueChanged<HomeQuickAction> onOpenAction;
  final VoidCallback onCloseAction;
  final String eventName;
  final String barName;
  final VoidCallback onOpenEventHub;
  final VoidCallback onOpenEvents;
  final VoidCallback onOpenBars;
  final ValueChanged<String> onOpenExternalUrl;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        QuickActions(onOpen: onOpenAction),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 260),
          transitionBuilder: (child, animation) {
            final offset = Tween<Offset>(
              begin: const Offset(0, -0.06),
              end: Offset.zero,
            ).animate(
              CurvedAnimation(parent: animation, curve: Curves.easeOutCubic),
            );
            return FadeTransition(
              opacity: animation,
              child: SlideTransition(position: offset, child: child),
            );
          },
          child: activeAction == null
              ? const SizedBox.shrink()
              : Padding(
                  key: ValueKey(activeAction!.route),
                  padding: const EdgeInsets.only(top: ToreTokens.s12),
                  child: HomeActionPanel(
                    action: activeAction!,
                    onOpenFull: () => Navigator.pushNamed(context, activeAction!.route),
                    onClose: onCloseAction,
                  ),
                ),
        ),
        const SizedBox(height: ToreTokens.s16),
        SectionHeader(title: 'Live maintenant', actionLabel: 'Events', onTap: onOpenEvents),
        HomeEventCard(
          title: eventName,
          bar: barName,
          meta: 'Live maintenant · entrée gratuite',
          onTap: onOpenEventHub,
        ),
        const SizedBox(height: ToreTokens.s16),
        NearbyEventsPreview(onOpenEvent: onOpenEvents),
        const SizedBox(height: ToreTokens.s16),
        SectionHeader(title: 'Bars proches', actionLabel: 'Voir tout', onTap: onOpenBars),
        BarsPreview(onBarTap: onOpenBars, onOpenMap: onOpenExternalUrl),
      ],
    );
  }
}

class MarketsTab extends StatelessWidget {
  const MarketsTab({
    super.key,
    required this.global,
    required this.event,
    required this.onGlobal,
    required this.onEvent,
  });

  final List<PolymarketDto> global;
  final List<PolymarketDto> event;
  final VoidCallback onGlobal;
  final VoidCallback onEvent;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(title: 'Bets globaux', actionLabel: 'Ouvrir', onTap: onGlobal),
        for (final item in global) BetCard(title: item.title, odds: '62%', onTap: onGlobal),
        const SizedBox(height: ToreTokens.s12),
        SectionHeader(title: 'Bets soirée', actionLabel: 'Live', onTap: onEvent),
        for (final item in event) BetCard(title: item.title, odds: '1.8x', onTap: onEvent),
      ],
    );
  }
}

class BetCard extends StatelessWidget {
  const BetCard({super.key, required this.title, required this.odds, required this.onTap});

  final String title;
  final String odds;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: ToreTokens.s8),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Row(
              children: [
                const Icon(Icons.show_chart, color: ToreTokens.yellowCta),
                const SizedBox(width: ToreTokens.s12),
                Expanded(
                  child: Text(title, style: Theme.of(context).textTheme.titleMedium),
                ),
                ToreBadge(label: odds, color: ToreTokens.rubyDeep),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HomeActionPanel extends StatelessWidget {
  const HomeActionPanel({
    super.key,
    required this.action,
    required this.onOpenFull,
    required this.onClose,
  });

  final HomeQuickAction action;
  final VoidCallback onOpenFull;
  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    final copy = HomeActionCopy.forRoute(action.route);
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onOpenFull,
      child: Card(
        color: ToreTokens.surfaceAlt,
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: ToreTokens.ruby.withValues(alpha: 0.22),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(action.icon, color: ToreTokens.yellowCta),
                  ),
                  const SizedBox(width: ToreTokens.s12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(copy.title, style: Theme.of(context).textTheme.titleMedium),
                        Text(copy.subtitle),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Fermer',
                    onPressed: onClose,
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              const SizedBox(height: ToreTokens.s12),
              Wrap(
                spacing: ToreTokens.s8,
                runSpacing: ToreTokens.s8,
                children: [
                  for (final chip in copy.chips)
                    Chip(
                      label: Text(chip),
                      backgroundColor: ToreTokens.black,
                      side: const BorderSide(color: ToreTokens.ruby),
                    ),
                ],
              ),
              const SizedBox(height: ToreTokens.s12),
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: onOpenFull,
                child: Container(
                  constraints: const BoxConstraints(minHeight: 46),
                  decoration: BoxDecoration(
                    color: ToreTokens.ruby,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(copy.ctaIcon, color: Colors.white),
                      const SizedBox(width: ToreTokens.s8),
                      Text(
                        copy.cta,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class HomeActionCopy {
  const HomeActionCopy({
    required this.title,
    required this.subtitle,
    required this.chips,
    required this.cta,
    required this.ctaIcon,
  });

  final String title;
  final String subtitle;
  final List<String> chips;
  final String cta;
  final IconData ctaIcon;

  static HomeActionCopy forRoute(String route) {
    switch (route) {
      case AppRoutes.join:
        return const HomeActionCopy(
          title: 'Rejoindre la soirée',
          subtitle: 'QR valide ou code manuel. Accès en un geste.',
          chips: ['Afond Night', 'Entrée gratuite', 'Pass actif'],
          cta: 'Ouvrir le join',
          ctaIcon: Icons.group_add,
        );
      case AppRoutes.menu:
        return const HomeActionCopy(
          title: 'Menu express',
          subtitle: 'Ajoute au panier, confirme, puis montre le QR au bar.',
          chips: ['2 taps max', 'Panier inline', 'QR commande'],
          cta: 'Commander',
          ctaIcon: Icons.local_bar,
        );
      case AppRoutes.wallet:
        return const HomeActionCopy(
          title: 'Wallet',
          subtitle: 'Solde, tickets et historique de la soirée.',
          chips: ['€129.20', 'Tickets prêts', 'Top-up'],
          cta: 'Voir le wallet',
          ctaIcon: Icons.account_balance_wallet,
        );
      case AppRoutes.safeKit:
        return const HomeActionCopy(
          title: 'Safe Kit',
          subtitle: 'Aide discrète, buddy check et contact staff.',
          chips: ['Alerte discrète', 'Buddy OK', 'Staff 2 min'],
          cta: 'Ouvrir Safe Kit',
          ctaIcon: Icons.health_and_safety,
        );
      case AppRoutes.ranking:
        return const HomeActionCopy(
          title: 'Ranking live',
          subtitle: 'Classement de la soirée et progression équipe.',
          chips: ['#12', '+3 places', '940 pts'],
          cta: 'Voir le classement',
          ctaIcon: Icons.leaderboard,
        );
      default:
        return const HomeActionCopy(
          title: 'Action TORÈ',
          subtitle: 'Module prêt pour la soirée.',
          chips: ['LIVE', 'BETA'],
          cta: 'Ouvrir',
          ctaIcon: Icons.arrow_forward,
        );
    }
  }
}

class HomeEventCard extends StatelessWidget {
  const HomeEventCard({
    super.key,
    required this.title,
    required this.bar,
    required this.meta,
    required this.onTap,
  });

  final String title;
  final String bar;
  final String meta;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(ToreTokens.s16),
          child: Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: ToreTokens.rubyDeep,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.local_fire_department, color: ToreTokens.yellowCta),
              ),
              const SizedBox(width: ToreTokens.s12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: ToreTokens.s4),
                    Text(bar, style: const TextStyle(color: Colors.white70)),
                    Text(meta, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                  ],
                ),
              ),
              const Icon(Icons.arrow_forward_ios, color: ToreTokens.yellowCta, size: 16),
            ],
          ),
        ),
      ),
    );
  }
}
