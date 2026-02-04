import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../bars/presentation/bars_screen.dart';
import '../../menu_market/presentation/menu_screen.dart';
import '../../wallet/presentation/wallet_screen.dart';

class HomeHubScreen extends ConsumerWidget {
  const HomeHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('TORÈ'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _CardLink(
            icon: Icons.near_me_outlined,
            title: 'Bars à proximité',
            subtitle: 'Trouver des bars autour de toi',
            onTap: () {
              // V1: on réutilise l’explorer (BarsScreen). Nearby arrive côté backend.
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const BarsScreen()),
              );
            },
          ),
          const SizedBox(height: 12),
          _CardLink(
            icon: Icons.map_outlined,
            title: 'Tous les bars',
            subtitle: 'Par ville / recherche',
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const BarsScreen()),
              );
            },
          ),
          const SizedBox(height: 12),
          _CardLink(
            icon: Icons.local_bar_outlined,
            title: 'Catalogue boissons',
            subtitle: 'Bientôt : bières, cocktails, softs…',
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Catalogue: à venir (V1.5)')),
              );
            },
          ),
          const SizedBox(height: 12),
          _CardLink(
            icon: Icons.qr_code_scanner_outlined,
            title: 'Check-in',
            subtitle: 'Ajouter une conso (hors bar possible)',
            onTap: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Check-in: à brancher (V1)')),
              );
            },
          ),

          const SizedBox(height: 20),
          if (ctx.hasActiveEvent) ...[
            Text(
              'Mode Event',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            _CardLink(
              icon: Icons.restaurant_menu_outlined,
              title: 'Menu Event',
              subtitle: 'Commander dans l’event actif',
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => MenuScreen(eventId: ctx.activeEventId!)),
                );
              },
            ),
            const SizedBox(height: 12),
            _CardLink(
              icon: Icons.account_balance_wallet_outlined,
              title: 'Wallet / Tickets',
              subtitle: 'Solde tickets + historique',
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => WalletScreen(eventId: ctx.activeEventId!)),
                );
              },
            ),
          ] else ...[
            Text(
              'Mode Libre',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            const Text(
              'Sélectionne un bar puis un event pour accéder au menu et au wallet.',
            ),
          ],
        ],
      ),
    );
  }
}

class _CardLink extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _CardLink({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              Icon(icon),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Text(subtitle),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}
