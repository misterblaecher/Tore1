import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'features/events/presentation/event_config_providers.dart';
import 'features/navigation/presentation/home_hub_screen.dart';
import 'features/navigation/presentation/polymarket_tab_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';
import 'features/navigation/presentation/ticker_screen.dart';
import 'features/qr/presentation/qr_scanner_screen.dart';
import 'shared/widgets/network_banner.dart';

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
    final appCtx = ref.watch(appContextProvider);

    final eventId = appCtx.activeEventId;
    final eventConfig = eventId != null ? ref.watch(eventConfigProvider(eventId)) : null;

    final showTickerTab = eventConfig?.maybeWhen(
          data: (cfg) => cfg.menuEnabled || cfg.walletEnabled || cfg.polymarketEnabled,
          orElse: () => true,
        ) ?? true;
    final showPolymarketTab = eventConfig?.maybeWhen(
          data: (cfg) => cfg.polymarketEnabled,
          orElse: () => true,
        ) ?? true;

    final tabs = <_ShellTab>[
      _ShellTab(
        key: _homeNavKey,
        icon: Icons.home_outlined,
        label: 'Home',
        root: const HomeHubScreen(),
      ),
      if (showTickerTab)
        _ShellTab(
          key: _tickerNavKey,
          icon: Icons.stacked_line_chart_outlined,
          label: 'Ticker',
          root: const TickerScreen(),
        ),
      if (showPolymarketTab)
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

    final leftTabs = tabs.take((tabs.length / 2).ceil()).toList();
    final rightTabs = tabs.skip(leftTabs.length).toList();

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
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
      floatingActionButton: FloatingActionButton(
        onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QrScannerScreen())),
        tooltip: 'Scanner QR',
        child: const Icon(Icons.qr_code_scanner_outlined),
      ),
      bottomNavigationBar: BottomAppBar(
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
              const SizedBox(width: 56),
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
