import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api.dart';
import '../../../state.dart';

enum CalendarRange { today, week, month }

DateTimeRange calendarWindow(CalendarRange range) {
  final now = DateTime.now();
  final start = DateTime(now.year, now.month, now.day);
  switch (range) {
    case CalendarRange.today:
      return DateTimeRange(start: start, end: start.add(const Duration(days: 1)));
    case CalendarRange.week:
      return DateTimeRange(start: start, end: start.add(const Duration(days: 7)));
    case CalendarRange.month:
      return DateTimeRange(start: start, end: DateTime(start.year, start.month + 1, start.day));
  }
}

class DateTimeRange {
  final DateTime start;
  final DateTime end;

  const DateTimeRange({required this.start, required this.end});
}

final eventMapProvider = FutureProvider.family<EventMapFetchResult, int>((ref, eventId) async {
  return ref.read(apiProvider).getEventMapWithCacheStatus(eventId);
});

final calendarEventsProvider = FutureProvider.family<CalendarEventsFetchResult, CalendarRange>((ref, range) async {
  final window = calendarWindow(range);
  return ref.read(apiProvider).getCalendarEventsWithCacheStatus(from: window.start, to: window.end);
});
