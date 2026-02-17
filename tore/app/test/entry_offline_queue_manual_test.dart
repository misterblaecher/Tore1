import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/entry/data/entry_offline_queue.dart';

void main() {
  test('EntryQueueItem serialize/restore supports MANUAL type', () {
    final item = EntryQueueItem(
      id: 'm1',
      eventId: 42,
      type: 'MANUAL',
      scannedAt: DateTime.parse('2026-01-01T00:00:00Z'),
      idempotencyKey: 'idem-manual-1',
      delta: 5,
      reason: 'QR illisible',
      note: 'porte A',
    );

    final copy = EntryQueueItem.fromJson(item.toJson());
    expect(copy.type, 'MANUAL');
    expect(copy.delta, 5);
    expect(copy.reason, 'QR illisible');
    expect(copy.note, 'porte A');
  });
}
