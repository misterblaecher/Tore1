import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'features/navigation/presentation/home_territory_feed_screen.dart';
import 'features/navigation/presentation/events_discovery_screen.dart';
import 'features/navigation/presentation/polymarket_tab_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';
import 'features/qr/presentation/qr_scanner_screen.dart';
import 'shared/widgets/network_banner.dart';
import 'ui/app_design_system.dart';
import 'core/auth/providers.dart';
import 'features/auth/presentation/email_auth_screen.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;

  final _homeNavKey = GlobalKey<NavigatorState>();
  final _tickerNavKey = GlobalKey<NavigatorState>();
  final _polymarketNavKey = GlobalKey<NavigatorState>();
  final _profileNavKey = GlobalKey<NavigatorState>();

  Widget _tabNavigator(GlobalKey<NavigatorState> key, Widget root) {
    return Navigator(key: key, onGenerateRoute: (_) => MaterialPageRoute(builder: (_) => root));
  }

  Future<void> _openScan(bool isGuest) async {
    if (isGuest) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Connecte-toi pour continuer.")),
      );
      return;
    }
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen()));
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(appContextInitProvider);
    final session = ref.watch(authSessionProvider);
    final isGuest = session.isGuest;
    final tabs = <_ShellTab>[
      _ShellTab(
        key: _homeNavKey,
        icon: Icons.home_outlined,
        label: 'Home',
        root: const HomeTerritoryFeedScreen(),
      ),
      _ShellTab(
        key: _tickerNavKey,
        icon: Icons.event_outlined,
        label: 'Events',
        root: const EventsDiscoveryScreen(),
      ),
      _ShellTab(
          key: _polymarketNavKey,
          icon: Icons.candlestick_chart_outlined,
          label: 'Polymarket',
          root: const PolymarketTabScreen(),
        ),
      _ShellTab(
        key: _profileNavKey,
        icon: Icons.person_outline,
        label: 'Profil',
        root: const ProfileScreen(),
      ),
    ];

    if (_index >= tabs.length) _index = 0;

    final leftTabs = tabs.take(2).toList();
    final rightTabs = tabs.skip(2).toList();

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            const ToreNetworkBanner(),
            Expanded(
              child: IndexedStack(
                index: _index,
                children: [for (final tab in tabs) _tabNavigator(tab.key, tab.root)],
              ),
            ),
          ],
        ),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: FloatingActionButton.large(
        backgroundColor: AppColors.accentGold,
        foregroundColor: Colors.black,
        elevation: 16,
        onPressed: () => _openScan(isGuest),
        tooltip: 'Scan',
        child: Container(
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(color: Color(0x88F4B400), blurRadius: 24, spreadRadius: 1),
            ],
          ),
          child: const Icon(Icons.qr_code_scanner_outlined, size: 32),
        ),
      ),
      bottomNavigationBar: BottomAppBar(
        color: AppColors.surface,
        shape: const CircularNotchedRectangle(),
        child: SizedBox(
          height: 64,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              for (final tab in leftTabs)
                _TabButton(
                  icon: tab.icon,
                  label: tab.label,
                  active: _index == tabs.indexOf(tab),
                  onTap: () => setState(() => _index = tabs.indexOf(tab)),
                ),
              const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(height: 30),
                  Text('Scan', style: TextStyle(fontSize: 12, color: AppColors.accentGold)),
                ],
              ),
              for (final tab in rightTabs)
                _TabButton(
                  icon: tab.icon,
                  label: tab.label,
                  active: _index == tabs.indexOf(tab),
                  onTap: () => setState(() => _index = tabs.indexOf(tab)),
                ),
            ],
          ),
        ),
      ),
      persistentFooterButtons: isGuest
          ? [
              TextButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EmailAuthScreen())),
                icon: const Icon(Icons.lock_open_outlined),
                label: const Text("Connecte-toi pour l'accès complet"),
              ),
            ]
          : null,
    );
  }
}

class _ShellTab {
  const _ShellTab({required this.key, required this.icon, required this.label, required this.root});

  final GlobalKey<NavigatorState> key;
  final IconData icon;
  final String label;
  final Widget root;
}

class _TabButton extends StatelessWidget {
  const _TabButton({required this.icon, required this.label, required this.active, required this.onTap});
  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = active ? Theme.of(context).colorScheme.secondary : null;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
        child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(icon, color: color), const SizedBox(height: 2), Text(label, style: TextStyle(fontSize: 12, color: color))]),
      ),
    );
  }
}
