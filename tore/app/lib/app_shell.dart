import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
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

  List<GlobalKey<NavigatorState>> get _navKeys => [
        _homeNavKey,
        _tickerNavKey,
        _polymarketNavKey,
        _profileNavKey,
      ];

  Widget _tabNavigator(GlobalKey<NavigatorState> key, Widget root) {
    return Navigator(
      key: key,
      onGenerateRoute: (_) => MaterialPageRoute(builder: (_) => root),
    );
  }

  Future<bool> _onWillPop() async {
    final nav = _navKeys[_index].currentState;
    if (nav != null && nav.canPop()) {
      nav.pop();
      return false;
    }
    if (_index != 0) {
      setState(() => _index = 0);
      return false;
    }
    return true;
  }

  void _onTapTab(int i) {
    if (i == _index) {
      _navKeys[i].currentState?.popUntil((r) => r.isFirst);
    } else {
      setState(() => _index = i);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(appContextInitProvider);
    final ctx = ref.watch(appContextProvider);

    final tabs = [
      _tabNavigator(_homeNavKey, const HomeHubScreen()),
      _tabNavigator(_tickerNavKey, const TickerScreen()),
      _tabNavigator(_polymarketNavKey, const PolymarketTabScreen()),
      _tabNavigator(_profileNavKey, const ProfileScreen()),
    ];

    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        body: SafeArea(
          child: Column(
            children: [
              if (ctx.hasActiveEvent)
                Material(
                  color: Theme.of(context).colorScheme.secondary.withOpacity(0.15),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    child: Row(
                      children: [
                        const Icon(Icons.bolt_outlined, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Event : ${ctx.activeEventName ?? '#${ctx.activeEventId}'}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        TextButton(
                          onPressed: () => ref.read(appContextProvider.notifier).leaveEvent(),
                          child: const Text('QUITTER'),
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: IndexedStack(index: _index, children: tabs),
              ),
            ],
          ),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
        floatingActionButton: FloatingActionButton(
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const QrScannerScreen()),
            );
          },
          child: const Icon(Icons.qr_code_scanner_outlined),
        ),
        bottomNavigationBar: BottomAppBar(
          shape: const CircularNotchedRectangle(),
          child: SizedBox(
            height: 64,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _TabButton(icon: Icons.home_outlined, label: 'Home', active: _index == 0, onTap: () => _onTapTab(0)),
                _TabButton(icon: Icons.toll_outlined, label: 'Ticker', active: _index == 1, onTap: () => _onTapTab(1)),
                const SizedBox(width: 44),
                _TabButton(icon: Icons.casino_outlined, label: 'Polymarket', active: _index == 2, onTap: () => _onTapTab(2)),
                _TabButton(icon: Icons.person_outline, label: 'Profil', active: _index == 3, onTap: () => _onTapTab(3)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TabButton extends StatelessWidget {
  const _TabButton({
    required this.icon,
    required this.label,
    required this.active,
    required this.onTap,
  });

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
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color),
            const SizedBox(height: 2),
            Text(label, style: TextStyle(fontSize: 12, color: color)),
          ],
        ),
      ),
    );
  }
}
