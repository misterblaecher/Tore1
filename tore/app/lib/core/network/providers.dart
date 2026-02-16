import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../config/app_config.dart';
import 'api_client.dart';

final appConfigProvider = Provider<AppConfig>((ref) {
  return AppConfig.fromDartDefines();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final appConfig = ref.watch(appConfigProvider);
  return ApiClient.create(baseUrl: appConfig.apiBaseUrl);
});
