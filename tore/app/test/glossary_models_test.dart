import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/glossary/glossary_models.dart';

void main() {
  test('parses glossary term', () {
    final term = GlossaryTerm.fromJson({
      'id': 7,
      'committeeId': 3,
      'yearId': 11,
      'term': 'Guindaille',
      'definition': 'Fête étudiante',
      'examples': 'On sort en guindaille',
      'tags': ['chants', 'tradition'],
      'isOfficial': true,
      'status': 'ACTIVE',
      'createdAt': '2026-01-01T10:00:00Z',
      'updatedAt': '2026-01-02T10:00:00Z',
    });

    expect(term.id, 7);
    expect(term.isOfficial, isTrue);
    expect(term.tags.length, 2);
  });

  test('parses glossary settings', () {
    final settings = GlossarySettings.fromJson({'public_enabled': true, 'availableTags': ['A', 'B']});
    expect(settings.publicEnabled, isTrue);
    expect(settings.availableTags, ['A', 'B']);
  });
}
