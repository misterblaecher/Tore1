import 'package:flutter/material.dart';

import '../../models/rebuild_types.dart';
import '../theme/tore_theme.dart';
import '../widgets/primitives.dart';
import 'top_icon_button.dart';
import 'wallet_top_button.dart';

class ToreShellTopBar extends StatelessWidget implements PreferredSizeWidget {
  const ToreShellTopBar({
    super.key,
    required this.network,
    required this.onOpenProfile,
    required this.onOpenNotifications,
    required this.onOpenWallet,
    this.walletBalance,
    this.unreadCount = 0,
    this.avatarImage,
  });

  final ConnectivityState network;
  final VoidCallback onOpenProfile;
  final VoidCallback onOpenNotifications;
  final VoidCallback onOpenWallet;
  final double? walletBalance;
  final int unreadCount;
  final ImageProvider<Object>? avatarImage;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    final ImageProvider<Object> resolvedAvatar =
        avatarImage ?? const AssetImage('assets/branding/App_Icon_NEW.png');

    return AppBar(
      leadingWidth: 64,
      leading: Padding(
        padding: const EdgeInsets.only(left: ToreTokens.s12),
        child: InkWell(
          borderRadius: BorderRadius.circular(999),
          onTap: onOpenProfile,
          child: Center(
            child: CircleAvatar(
              radius: 18,
              backgroundColor: ToreTokens.surfaceAlt,
              backgroundImage: resolvedAvatar,
            ),
          ),
        ),
      ),
      titleSpacing: 0,
      title: Row(
        children: [
          Image.asset('assets/branding/logo_minimal.png', width: 28, height: 28),
          const SizedBox(width: ToreTokens.s8),
          const Text('TORÈ'),
        ],
      ),
      actions: [
        Padding(
          padding: const EdgeInsets.only(right: ToreTokens.s8),
          child: Center(
            child: ToreBadge(
              label: network == ConnectivityState.online ? 'LIVE' : 'OFFLINE',
              color:
                  network == ConnectivityState.online ? ToreTokens.ruby : ToreTokens.warning,
            ),
          ),
        ),
        TopIconButton(
          icon: Icons.notifications_none,
          tooltip: 'Notifications',
          onPressed: onOpenNotifications,
          badgeCount: unreadCount,
        ),
        const SizedBox(width: ToreTokens.s8),
        WalletTopButton(onPressed: onOpenWallet, balance: walletBalance),
        const SizedBox(width: ToreTokens.s12),
      ],
    );
  }
}
