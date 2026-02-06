import 'package:dio/dio.dart';
import '../../../shared/models/created_event.dart';
import '../../../shared/models/event.dart';
import '../../../shared/models/qr_pack.dart';

class EventsRepository {
  final Dio _dio;
  EventsRepository(this._dio);

  Future<List<Event>> fetchEvents(int barId) async {
    final res = await _dio.get('/bars/$barId/events');
    final data = (res.data as List).cast<dynamic>();
    return data
        .map((e) => Event.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<CreatedEvent> createEvent({
    required String name,
    required DateTime startsAt,
    required DateTime endsAt,
    int? barId,
    String? city,
  }) async {
    final res = await _dio.post(
      '/events',
      data: {
        'name': name,
        'starts_at': startsAt.toIso8601String(),
        'ends_at': endsAt.toIso8601String(),
        if (barId != null) 'bar_id': barId,
        if (city != null && city.isNotEmpty) 'city': city,
      },
    );
    return CreatedEvent.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  Future<QrPack> fetchQrPack(int eventId) async {
    final res = await _dio.get('/events/$eventId/qr-pack');
    return QrPack.fromJson(Map<String, dynamic>.from(res.data as Map));
  }
}
