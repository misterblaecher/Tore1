import 'package:dio/dio.dart';

import '../../../shared/models/event_config.dart';

class EventConfigService {
  EventConfigService(this._dio);

  final Dio _dio;

  Future<EventConfig> fetchEventConfig(int eventId) async {
    final res = await _dio.get('/events/$eventId/config');
    return EventConfig.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<EventConfig> patchEventConfig(int eventId, Map<String, dynamic> payload) async {
    final res = await _dio.patch('/events/$eventId/config', data: payload);
    return EventConfig.fromJson(Map<String, dynamic>.from(res.data as Map));
  }
}
