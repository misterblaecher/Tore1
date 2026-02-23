import '../models/qr_resolve.dart';
import 'api_client.dart';

abstract class ContractApi {
  Future<QrResolve> resolveQr(String payload);
}

class RebuildContractApi implements ContractApi {
  RebuildContractApi(this._apiClient);

  final ApiClient _apiClient;

  @override
  Future<QrResolve> resolveQr(String payload) => _apiClient.resolveQr(payload);
}
