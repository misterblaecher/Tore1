import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state.dart';
import '../../core/network/error_mapper.dart';
import 'ticker_models.dart';

final tickerProvider =
    FutureProvider.autoDispose.family<List<TickerItem>, int>((ref, eventId) async {
  final link = ref.keepAlive();
  Timer(const Duration(seconds: 45), link.close);

  final api = ref.watch(apiProvider);
  final raw = await api.ticker(eventId);
  final items = raw.cast<Map<String, dynamic>>();
  final parsed = items.map(TickerItem.fromJson).toList();
  parsed.sort((a, b) => b.ts.compareTo(a.ts));
  return parsed;
});

/// Small helper: translate errors for UI.
final tickerErrorMessageProvider = Provider<String Function(Object)>((ref) {
  return (e) => ErrorMapper.message(e);
});
