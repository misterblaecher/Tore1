import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_context/app_context.dart';
import '../../market/market_screen.dart';

class PolymarketTabScreen extends ConsumerWidget {
  const PolymarketTabScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(appContextProvider);
    if (!ctx.hasActiveEvent) {
      return const Scaffold(
        body: Center(
          child: Padding(
            padding: EdgeInsets.all(20),
            child: Text('Scanne un QR event pour activer Polymarket.'),
          ),
        ),
      );
    }
    return MarketScreen(eventId: ctx.activeEventId!);
  }
}
