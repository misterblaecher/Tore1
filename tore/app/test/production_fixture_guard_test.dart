import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('active production path contains no known showcase fallback', () {
    const activePaths = [
      'lib/main.dart',
      'lib/tore_mvp_app.dart',
      'lib/features/discovery',
      'lib/features/events/presentation/event_detail_screen.dart',
      'lib/features/bars',
      'lib/features/navigation/presentation/profile_screen.dart',
    ];
    const forbidden = [
      'event_42',
      'Afond Night',
      'TORÈ Test Bar',
      '_applyShowcaseDefaults',
      'fetchMeSnapshot',
      'ToreRebuildApp',
      "rebuild/ui/theme/tore_theme.dart",
    ];

    final files = <File>[];
    for (final path in activePaths) {
      final type = FileSystemEntity.typeSync(path);
      if (type == FileSystemEntityType.file) {
        files.add(File(path));
      } else if (type == FileSystemEntityType.directory) {
        files.addAll(Directory(path)
            .listSync(recursive: true)
            .whereType<File>()
            .where((file) => file.path.endsWith('.dart')));
      }
    }

    final productionSource =
        files.map((file) => file.readAsStringSync()).join();
    for (final value in forbidden) {
      expect(productionSource, isNot(contains(value)), reason: value);
    }
  });
}
