import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'features/events/presentation/event_config_providers.dart';
import 'features/navigation/presentation/home_hub_screen.dart';
import 'features/navigation/presentation/polymarket_tab_screen.dart';
import 'features/navigation/presentation/ticker_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';
import 'features/qr/presentation/qr_scanner_screen.dart';

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

  @override
  Widget build(BuildContext context) {
    ref.watch(appContextInitProvider);
    final ctx = ref.watch(appContextProvider);
    final configAsync = ctx.hasActiveEvent ? ref.watch(eventConfigProvider(ctx.activeEventId!)) : null;
    final showTicker = configAsync?.maybeWhen(
          data: (cfg) => cfg.menuEnabled || cfg.walletEnabled || cfg.polymarketEnabled,
          orElse: () => true,
        ) ??
        true;

    final tabs = <Widget>[
      _tabNavigator(_homeNavKey, const HomeHubScreen()),
      if (showTicker) _tabNavigator(_tickerNavKey, const TickerScreen()),
      _tabNavigator(_polymarketNavKey, const PolymarketTabScreen()),
      _tabNavigator(_profileNavKey, const ProfileScreen()),
    ];

    final entries = <({IconData icon, String label})>[
      (icon: Icons.home_outlined, label: 'Home'),
      if (showTicker) (icon: Icons.toll_outlined, label: 'Ticker'),
      (icon: Icons.casino_outlined, label: 'Polymarket'),
      (icon: Icons.person_outline, label: 'Profil'),
    ];
    if (_index >= tabs.length) _index = 0;

    return Scaffold(
      body: SafeArea(child: IndexedStack(index: _index, children: tabs)),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      floatingActionButton: FloatingActionButton(
        onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen())),
        child: const Icon(Icons.qr_code_scanner_outlined),
      ),
      bottomNavigationBar: BottomAppBar(
        shape: const CircularNotchedRectangle(),
        child: SizedBox(
          height: 64,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              for (var i = 0; i < entries.length; i++)
                _TabButton(
                  icon: entries[i].icon,
                  label: entries[i].label,
                  active: _index == i,
                  onTap: () => setState(() => _index = i),
                ),
            ],
          ),
        ),
      ),
    );
  }
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
