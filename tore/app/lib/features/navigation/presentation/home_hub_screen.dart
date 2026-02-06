import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../bars/presentation/bars_screen.dart';
import '../../menu_market/presentation/menu_screen.dart';
import '../../wallet/presentation/wallet_screen.dart';
import '../../qr/presentation/qr_scanner_screen.dart';
import '../../events/presentation/event_config_providers.dart';
import '../../events/presentation/create_event_screen.dart';
import '../../events/presentation/qr_pack_screen.dart';
import '../../reports/presentation/report_screen.dart';
import '../../../shared/cache/offline_no_cache_exception.dart';
import 'checkin_screen.dart';

class HomeHubScreen extends ConsumerWidget {
  const HomeHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    final configAsync = ctx.hasActiveEvent
        ? ref.watch(eventConfigProvider(ctx.activeEventId!))
        : null;
    final config = configAsync?.maybeWhen(
      data: (value) => value,
      orElse: () => null,
    );
    final configOfflineLimited = configAsync?.maybeWhen(
          error: (err, _) => err is OfflineNoCacheException,
          orElse: () => false,
        ) ??
        false;

    final menuEnabled = configOfflineLimited ? true : (config?.menuEnabled ?? true);
    final walletEnabled = configOfflineLimited ? false : (config?.walletEnabled ?? true);
    final entryEnabled = configOfflineLimited ? false : (config?.entryEnabled ?? false);
    final checkinEnabled = configOfflineLimited ? false : (config?.checkinEnabled ?? false);
    final reportEnabled = configOfflineLimited ? false : (config?.reportEnabled ?? false);
    final isAdmin = (config?.role ?? '') == 'admin';

    return Scaffold(
      appBar: AppBar(
        title: const Text('TORÈ'),
        actions: [
          IconButton(
            tooltip: 'Scanner QR',
            icon: const Icon(Icons.qr_code_scanner_outlined),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const QrScannerScreen()),
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _CardLink(
            icon: Icons.qr_code_scanner_outlined,
            title: 'Scanner',
            subtitle: 'Scanner un QR pour rejoindre un event, menu ou entrée',
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const QrScannerScreen()),
              );
            },
          ),
          const SizedBox(height: 12),
          _CardLink(
            icon: Icons.event_available_outlined,
            title: 'Créer un event',
            subtitle: 'Nouveau event + QR Pack officiel',
            onTap: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const CreateEventScreen()),
              );
            },
          ),
          const SizedBox(height: 12),
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

          const SizedBox(height: 20),
          if (ctx.hasActiveEvent) ...[
            Text(
              'Mode Event',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            if (configOfflineLimited) ...[
              const _LimitedModeNotice(),
              const SizedBox(height: 12),
            ],
            _CardLink(
              icon: Icons.qr_code_2_outlined,
              title: 'QR Pack',
              subtitle: 'Accéder aux QR officiels',
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => QrPackScreen(eventId: ctx.activeEventId!),
                  ),
                );
              },
            ),
            const SizedBox(height: 12),
            if (reportEnabled && isAdmin) ...[
              _CardLink(
                icon: Icons.insert_chart_outlined,
                title: 'Rapport soirée',
                subtitle: 'Bilan ventes, coûts et export',
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => ReportScreen(eventId: ctx.activeEventId!),
                    ),
                  );
                },
              ),
              const SizedBox(height: 12),
            ],
            if (menuEnabled) ...[
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
            ],
            if (walletEnabled) ...[
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
              const SizedBox(height: 12),
            ],
            if (entryEnabled) ...[
              _CardLink(
                icon: Icons.qr_code_scanner_outlined,
                title: 'Entrée',
                subtitle: 'Scanner des accès pour l’event',
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const QrScannerScreen()),
                  );
                },
              ),
              const SizedBox(height: 12),
            ],
            if (checkinEnabled)
              _CardLink(
                icon: Icons.qr_code_scanner_outlined,
                title: 'Check-in',
                subtitle: 'Ajouter une conso',
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const CheckinScreen()),
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

class _LimitedModeNotice extends StatelessWidget {
  const _LimitedModeNotice();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.blueGrey.shade100,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            const Icon(Icons.info_outline),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Mode limité : configuration indisponible hors-ligne.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
