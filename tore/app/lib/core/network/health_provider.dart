import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'providers.dart';

final apiHealthProvider = FutureProvider<bool>((ref) async {
  final api = ref.read(apiClientProvider);

  try {
    final r = await api.dio.get('/docs'); // ton backend répond 200 ici
    final code = r.statusCode ?? 0;
    return code >= 200 && code < 300;
  } on DioException {
    return false;
  } catch (_) {
    return false;
  }
});
