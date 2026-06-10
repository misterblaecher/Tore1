import 'package:flutter/material.dart';

class ToreBottomNav extends StatelessWidget {
  const ToreBottomNav({
    super.key,
    required this.selectedIndex,
    required this.isConnectedAccount,
    required this.onDestinationSelected,
  });

  final int selectedIndex;
  final bool isConnectedAccount;
  final ValueChanged<int> onDestinationSelected;

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex:
          isConnectedAccount ? selectedIndex : selectedIndex.clamp(0, 3),
      destinations: [
        const NavigationDestination(icon: Icon(Icons.home), label: 'Hub'),
        const NavigationDestination(
          icon: Icon(Icons.candlestick_chart),
          label: 'Ticker',
        ),
        const NavigationDestination(
          icon: Icon(Icons.qr_code_scanner),
          label: 'Accès',
        ),
        const NavigationDestination(
          icon: Icon(Icons.show_chart),
          label: 'Bets',
        ),
        if (isConnectedAccount)
          const NavigationDestination(icon: Icon(Icons.forum), label: 'Forum'),
      ],
      onDestinationSelected: onDestinationSelected,
    );
  }
}
