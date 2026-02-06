import 'package:dio/dio.dart';

import '../../../shared/models/event_cost.dart';

class EventCostService {
  EventCostService(this._dio);

  final Dio _dio;

  Future<List<EventCost>> listCosts(int eventId) async {
    final res = await _dio.get('/events/$eventId/costs');
    final data = (res.data as List).cast<dynamic>();
    return data
        .map((e) => EventCost.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<EventCost> createCost({
    required int eventId,
    required String label,
    required int amountCents,
    required String category,
  }) async {
    final res = await _dio.post(
      '/events/$eventId/costs',
      data: {
        'label': label,
        'amount_cents': amountCents,
        'category': category,
      },
    );
    return EventCost.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<void> deleteCost({
    required int eventId,
    required int costId,
  }) async {
    await _dio.delete('/events/$eventId/costs/$costId');
  }
}
