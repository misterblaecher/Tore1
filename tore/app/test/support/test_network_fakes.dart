import 'package:tore/core/network/api_client.dart';
import 'package:tore/features/health/data/health_repository.dart';

class FakeHealthRepository extends HealthRepository {
  FakeHealthRepository() : super(ApiClient.create(baseUrl: 'http://localhost:1'));

  @override
  Future<bool> ping() async => true;

  @override
  Future<HealthCheckResult> pingWithPolicy({
    int maxRetries = 2,
    Duration connectTimeout = const Duration(seconds: 30),
    Duration receiveTimeout = const Duration(seconds: 45),
  }) async {
    return const HealthCheckResult(
      reachability: HealthReachability.online,
      endpoint: '/healthz',
      attempts: 1,
      latency: Duration(milliseconds: 1),
      statusCode: 200,
    );
  }
}
