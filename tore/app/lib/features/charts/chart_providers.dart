import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state.dart';
import 'chart_models.dart';
import 'chart_repository.dart';

final chartsRepositoryProvider = Provider<ChartsRepository>((ref) {
  final api = ref.watch(apiProvider);
  return ChartsRepository(api);
});

final eventMenuDrinksProvider = FutureProvider.autoDispose
    .family<List<MenuDrinkMeta>, int>((ref, eventId) async {
  final link = ref.keepAlive();
  Timer(const Duration(minutes: 2), link.close);

  final repo = ref.watch(chartsRepositoryProvider);
  return repo.fetchMenu(eventId);
});

class DrinkHistoryArgs {
  final int eventId;
  final int drinkId;
  final String range;

  const DrinkHistoryArgs(
      {required this.eventId, required this.drinkId, this.range = '24h'});

  @override
  bool operator ==(Object other) =>
      other is DrinkHistoryArgs &&
      other.eventId == eventId &&
      other.drinkId == drinkId &&
      other.range == range;

  @override
  int get hashCode => Object.hash(eventId, drinkId, range);
}

final drinkHistoryProvider = FutureProvider.autoDispose
    .family<List<PricePoint>, DrinkHistoryArgs>((ref, args) async {
  final link = ref.keepAlive();
  Timer(const Duration(minutes: 2), link.close);

  final repo = ref.watch(chartsRepositoryProvider);
  return repo.fetchHistory(
      eventId: args.eventId, drinkId: args.drinkId, range: args.range);
});

final topMoversProvider = FutureProvider.autoDispose
    .family<List<Map<String, dynamic>>, int>((ref, eventId) async {
  final link = ref.keepAlive();
  Timer(const Duration(minutes: 1), link.close);

  final repo = ref.watch(chartsRepositoryProvider);
  return repo.fetchTopMovers(eventId);
});
