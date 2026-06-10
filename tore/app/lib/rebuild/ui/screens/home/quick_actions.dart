import 'package:flutter/material.dart';

import '../../../routing/app_routes.dart';
import '../../theme/tore_theme.dart';

class HomeQuickAction {
  const HomeQuickAction(this.label, this.icon, this.route, {this.tabIndex});

  final String label;
  final IconData icon;
  final String route;
  final int? tabIndex;
}

class QuickActions extends StatelessWidget {
  const QuickActions({super.key, required this.onOpen});

  final ValueChanged<HomeQuickAction> onOpen;

  static const actions = [
    HomeQuickAction('Scanner', Icons.qr_code_scanner, AppRoutes.scanner, tabIndex: 2),
    HomeQuickAction('Join', Icons.group_add, AppRoutes.join),
    HomeQuickAction('Menu', Icons.local_bar, AppRoutes.menu),
    HomeQuickAction('Wallet', Icons.account_balance_wallet, AppRoutes.wallet),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: actions.length,
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 180,
        mainAxisSpacing: ToreTokens.s8,
        crossAxisSpacing: ToreTokens.s8,
        childAspectRatio: 2.35,
      ),
      itemBuilder: (context, index) {
        final action = actions[index];
        return TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: Duration(milliseconds: 180 + index * 45),
          curve: Curves.easeOutBack,
          builder: (context, value, child) {
            return Opacity(
              opacity: value.clamp(0.0, 1.0),
              child: Transform.translate(
                offset: Offset(0, (1 - value) * 10),
                child: Transform.scale(scale: 0.94 + value * 0.06, child: child),
              ),
            );
          },
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => onOpen(action),
            child: Container(
              decoration: BoxDecoration(
                color: ToreTokens.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: ToreTokens.border),
              ),
              child: Padding(
                padding: const EdgeInsets.all(ToreTokens.s12),
                child: Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: ToreTokens.ruby,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(action.icon, color: Colors.white, size: 19),
                    ),
                    const SizedBox(width: ToreTokens.s8),
                    Expanded(
                      child: Text(
                        action.label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
