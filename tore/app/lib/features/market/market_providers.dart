import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/core/network/api_client.dart';
import 'market_repository.dart';
import 'market_models.dart';

final marketRepositoryProvider = Provider<MarketRepository>((ref) {
  final api = ApiClient.create();
  return MarketRepository(api);
});

final marketMenuProvider =
    FutureProvider.family<List<MarketDrink>, int>((ref, eventId) async {
  final repo = ref.read(marketRepositoryProvider);
  return repo.fetchMenu(eventId: eventId);
});
