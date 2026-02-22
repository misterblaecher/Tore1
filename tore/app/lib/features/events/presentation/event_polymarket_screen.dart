import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../navigation/presentation/polymarket_tab_screen.dart';
import 'active_event_context_provider.dart';

class EventPolymarketScreen extends ConsumerWidget {
  const EventPolymarketScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ctx = ref.watch(activeEventContextProvider).valueOrNull;
    final permissions = ctx?.permissions ?? const EventPermissions(canCreateBets: false, canResolveBets: false);
    return PolymarketTabScreen(
      eventOnly: true,
      canCreateBets: permissions.canCreateBets,
      canResolveBets: permissions.canResolveBets,
    );
  }
}
