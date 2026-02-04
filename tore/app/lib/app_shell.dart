import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'features/navigation/presentation/home_hub_screen.dart';
import 'features/navigation/presentation/charts_screen.dart';
import 'features/navigation/presentation/checkin_screen.dart';
import 'features/navigation/presentation/ticker_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  int _index = 0;

  final _homeNavKey = GlobalKey<NavigatorState>();
  final _graphNavKey = GlobalKey<NavigatorState>();
  final _checkinNavKey = GlobalKey<NavigatorState>();
  final _tickerNavKey = GlobalKey<NavigatorState>();
  final _profileNavKey = GlobalKey<NavigatorState>();

  List<GlobalKey<NavigatorState>> get _navKeys => [
        _homeNavKey,
        _graphNavKey,
        _checkinNavKey,
        _tickerNavKey,
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
    // Restore last selected bar/event (non-blocking).
    ref.watch(appContextInitProvider);
    final ctx = ref.watch(appContextProvider);

    final tabs = [
      _tabNavigator(_homeNavKey, const HomeHubScreen()),
      _tabNavigator(_graphNavKey, const ChartsScreen()),
      _tabNavigator(_checkinNavKey, const CheckinScreen()),
      _tabNavigator(_tickerNavKey, const TickerScreen()),
      _tabNavigator(_profileNavKey, const ProfileScreen()),
    ];

    return WillPopScope(
      onWillPop: _onWillPop,
      child: Scaffold(
        // Bandeau global "Mode Event"
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
                          onPressed: () =>
                              ref.read(appContextProvider.notifier).leaveEvent(),
                          child: const Text('QUITTER'),
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: IndexedStack(
                  index: _index,
                  children: tabs,
                ),
              ),
            ],
          ),
        ),

        bottomNavigationBar: BottomNavigationBar(
          currentIndex: _index,
          onTap: _onTapTab,
          type: BottomNavigationBarType.fixed,
          items: const [
            BottomNavigationBarItem(
                icon: Icon(Icons.home_outlined), label: 'Accueil'),
            BottomNavigationBarItem(
                icon: Icon(Icons.show_chart_outlined), label: 'Graph'),
            BottomNavigationBarItem(
                icon: Icon(Icons.swap_vert_circle_outlined), label: 'Échanger'),
            BottomNavigationBarItem(icon: Icon(Icons.toll_outlined), label: 'Ticker'),
            BottomNavigationBarItem(
                icon: Icon(Icons.person_outline), label: 'Profil'),
          ],
        ),
      ),
    );
  }
}
