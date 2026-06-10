import 'package:flutter/material.dart';

import '../../../models/backend_models.dart';
import '../../../routing/app_routes.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/section_header.dart';
import 'access_actions.dart';
import 'access_quick_grid.dart';
import 'access_scan_frame.dart';
import 'active_order_card.dart';

class AccessScreen extends StatelessWidget {
  const AccessScreen({
    super.key,
    required this.onOpenScanner,
    required this.onTorch,
    required this.onManualCode,
    required this.onHelp,
    required this.onOpenRoute,
    required this.quickActions,
    this.activeOrder,
    this.zones = const [],
    this.torchOn = false,
  });

  final VoidCallback onOpenScanner;
  final VoidCallback onTorch;
  final VoidCallback onManualCode;
  final VoidCallback onHelp;
  final ValueChanged<String> onOpenRoute;
  final List<AccessQuickAction> quickActions;
  final OrderDto? activeOrder;
  final List<ZoneDto> zones;
  final bool torchOn;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('ACCÈS', style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: ToreTokens.s4),
        const Text(
          'Scanne un QR event, menu, WiFi ou invitation et garde les raccourcis utiles à portée.',
        ),
        const SizedBox(height: ToreTokens.s16),
        AccessScanFrame(onTap: onOpenScanner),
        const SizedBox(height: ToreTokens.s12),
        AccessActions(
          onTorch: onTorch,
          onManualCode: onManualCode,
          onHelp: onHelp,
          torchOn: torchOn,
        ),
        const SizedBox(height: ToreTokens.s16),
        SectionHeader(title: 'Accès rapides'),
        AccessQuickGrid(actions: quickActions, onOpenRoute: onOpenRoute),
        if (activeOrder != null) ...[
          const SizedBox(height: ToreTokens.s16),
          ActiveOrderCard(
            order: activeOrder!,
            zones: zones,
            onTap: () => onOpenRoute(AppRoutes.orders),
          ),
        ],
      ],
    );
  }
}
