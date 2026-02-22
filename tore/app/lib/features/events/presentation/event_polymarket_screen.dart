import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../navigation/presentation/polymarket_tab_screen.dart';
import 'active_event_context_provider.dart';

class EventPolymarketScreen extends ConsumerWidget {
  const EventPolymarketScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(activeEventContextProvider).valueOrNull;

    // On garde le calcul permissions pour usage futur,
    // mais on ne les passe pas au widget tant que son constructeur ne les accepte pas.
    final permissions = ctx?.permissions ??
        const EventPermissions(
          canCreateBets: false,
          canResolveBets: false,
        );

    return const PolymarketTabScreen();
  }
}