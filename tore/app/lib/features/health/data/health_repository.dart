import 'package:dio/dio.dart';
import '../../../core/network/api_client.dart';

class HealthRepository {
  final ApiClient api;

  HealthRepository(this.api);

  Future<bool> ping() async {
    // Dans ton backend: /docs répond 200, /health et / sont 404
    try {
      final r = await api.dio.get('/docs');
      final code = r.statusCode ?? 0;
      return code >= 200 && code < 300;
    } on DioException {
      return false;
    } catch (_) {
      return false;
    }
  }
}
