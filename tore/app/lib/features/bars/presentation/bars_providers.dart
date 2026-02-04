import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/providers.dart';
import '../data/bars_repository.dart';
import '../../../shared/models/bar.dart';

final barsRepositoryProvider = Provider<BarsRepository>((ref) {
  final client = ref.watch(apiClientProvider);
  return BarsRepository(client.dio);
});

final barsFutureProvider = FutureProvider<List<Bar>>((ref) async {
  final repo = ref.watch(barsRepositoryProvider);
  return repo.fetchBars();
});
