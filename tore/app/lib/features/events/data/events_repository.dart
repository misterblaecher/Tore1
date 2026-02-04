import 'package:dio/dio.dart';
import '../../../shared/models/event.dart';

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
}
