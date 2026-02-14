import 'package:dio/dio.dart';
import '../../../core/network/api_client.dart';

class HealthRepository {
  final ApiClient api;

  HealthRepository(this.api);

  Future<bool> ping() async {
    // Endpoint santé backend
    try {
      final r = await api.dio.get('/healthz');
      final code = r.statusCode ?? 0;
      return code >= 200 && code < 300;
    } on DioException {
      return false;
    } catch (_) {
      return false;
    }
  }
}
