import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_models.dart';

void main() {
  AppUser userWithMode(String mode) => AppUser.fromJson({
        'id': 'user-1',
        'display_name': 'Alex',
        'account_mode': mode,
      });

  test('mode capabilities are derived from the server account mode', () {
    final user = userWithMode('user');
    final organizer = userWithMode('organizer');
    final team = userWithMode('team');

    expect(user.canUseOrganizerMode, isFalse);
    expect(user.canUseBarMode, isFalse);
    expect(organizer.canUseOrganizerMode, isTrue);
    expect(organizer.canUseBarMode, isFalse);
    expect(team.canUseOrganizerMode, isFalse);
    expect(team.canUseBarMode, isTrue);
  });
}
