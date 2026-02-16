import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/api_client.dart';
import 'package:tore/core/perf/perf_tracer.dart';
import 'market_repository.dart';
import 'market_models.dart';

final marketRepositoryProvider = Provider<MarketRepository>((ref) {
  final api = ApiClient.create();
  return MarketRepository(api, ref.watch(perfTracerProvider));
});

final marketMenuProvider =
    FutureProvider.family<List<MarketDrink>, int>((ref, eventId) async {
  final repo = ref.read(marketRepositoryProvider);
  return repo.fetchMenu(eventId: eventId);
});
