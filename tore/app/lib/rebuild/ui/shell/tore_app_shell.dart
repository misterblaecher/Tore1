import 'package:flutter/material.dart';

import '../../models/rebuild_types.dart';
import 'tore_bottom_nav.dart';
import 'tore_shell_top_bar.dart';

class ToreAppShell extends StatelessWidget {
  const ToreAppShell({
    super.key,
    required this.mode,
    required this.network,
    required this.body,
    required this.onOpenProfile,
    required this.onOpenNotifications,
    required this.onOpenWallet,
    required this.onOpenAccess,
    this.walletBalance,
    this.selectedUserTab = 0,
    this.isConnectedAccount = false,
    this.onSelectUserTab,
  });

  final ToreMode mode;
  final ConnectivityState network;
  final Widget body;
  final VoidCallback onOpenProfile;
  final VoidCallback onOpenNotifications;
  final VoidCallback onOpenWallet;
  final VoidCallback onOpenAccess;
  final double? walletBalance;
  final int selectedUserTab;
  final bool isConnectedAccount;
  final ValueChanged<int>? onSelectUserTab;

  @override
  Widget build(BuildContext context) {
    final isUserMode = mode == ToreMode.user;
    return Scaffold(
      appBar: ToreShellTopBar(
        network: network,
        walletBalance: walletBalance,
        onOpenProfile: onOpenProfile,
        onOpenNotifications: onOpenNotifications,
        onOpenWallet: onOpenWallet,
      ),
      floatingActionButton: isUserMode
          ? FloatingActionButton(
              onPressed: onOpenAccess,
              child: const Icon(Icons.qr_code_scanner),
            )
          : null,
      bottomNavigationBar: isUserMode && onSelectUserTab != null
          ? ToreBottomNav(
              selectedIndex: selectedUserTab,
              isConnectedAccount: isConnectedAccount,
              onDestinationSelected: onSelectUserTab!,
            )
          : null,
      body: body,
    );
  }
}
