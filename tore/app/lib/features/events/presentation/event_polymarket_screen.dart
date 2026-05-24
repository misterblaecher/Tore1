import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../navigation/presentation/polymarket_tab_screen.dart';

class EventPolymarketScreen extends ConsumerWidget {
  const EventPolymarketScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const PolymarketTabScreen();
  }
}
