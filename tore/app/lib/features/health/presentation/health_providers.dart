import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/providers.dart';
import '../data/health_repository.dart';

final healthRepositoryProvider = Provider<HealthRepository>((ref) {
  final api = ref.read(apiClientProvider);
  return HealthRepository(api);
});

final healthProvider = FutureProvider<bool>((ref) async {
  final repo = ref.read(healthRepositoryProvider);
  return repo.ping();
});
