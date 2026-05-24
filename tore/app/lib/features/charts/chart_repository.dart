import '../../api.dart';
import 'chart_models.dart';

class ChartsRepository {
  final Api api;
  const ChartsRepository(this.api);

  Future<List<MenuDrinkMeta>> fetchMenu(int eventId) async {
    final raw = await api.menu(eventId);
    final items = (raw).cast<Map<String, dynamic>>();
    return items
        .map(MenuDrinkMeta.fromMenuRow)
        .where((d) => d.drinkId != 0)
        .toList();
  }

  Future<List<PricePoint>> fetchHistory({
    required int eventId,
    required int drinkId,
    String range = '24h',
  }) async {
    final raw = await api.drinkHistory(
        eventId: eventId, drinkId: drinkId, range: range);
    final points = <PricePoint>[];
    for (final row in raw) {
      final p = PricePoint.tryParse(row);
      if (p != null) points.add(p);
    }
    // Ensure chronological order if backend returned reverse.
    points.sort((a, b) => a.ts.compareTo(b.ts));
    return points;
  }

  Future<List<Map<String, dynamic>>> fetchTopMovers(int eventId) async {
    final raw = await api.topMovers(eventId);
    return raw.cast<Map<String, dynamic>>();
  }
}
