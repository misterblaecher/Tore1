import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state.dart';
import 'wallet_models.dart';

class WalletHistoryArgs {
  final int eventId;
  final String userId;
  final int limit;

  const WalletHistoryArgs({required this.eventId, required this.userId, this.limit = 50});

  @override
  bool operator ==(Object other) =>
      other is WalletHistoryArgs &&
      other.eventId == eventId &&
      other.userId == userId &&
      other.limit == limit;

  @override
  int get hashCode => Object.hash(eventId, userId, limit);
}

final walletHistoryProvider =
    FutureProvider.autoDispose.family<List<WalletHistoryEntry>, WalletHistoryArgs>((ref, args) async {
  final link = ref.keepAlive();
  Timer(const Duration(minutes: 2), link.close);

  final api = ref.watch(apiProvider);
  final page = await api.walletLedger(limit: args.limit);
  final raw = (page['items'] as List<dynamic>? ?? const []);
  final list = raw.cast<Map<String, dynamic>>();
  final entries = list.map(WalletHistoryEntry.fromJson).toList();
  entries.sort((a, b) => b.ts.compareTo(a.ts));
  return entries;
});
