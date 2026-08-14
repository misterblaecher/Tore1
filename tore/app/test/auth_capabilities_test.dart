import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_models.dart';
import 'package:tore/features/profile/domain/profile_models.dart';

void main() {
  test('account_mode is not treated as an authorization capability', () {
    final legacy = AppUser.fromJson({
      'id': 'user-1',
      'display_name': 'Alex',
      'account_mode': 'organizer',
    });
    expect(legacy.accountMode, AccountMode.organizer);

    final capabilities = EffectiveCapabilities.fromJson({
      'global_roles': ['USER'],
      'structures': [],
      'events': [],
      'bars': [],
      'modes': {'organizer': false, 'bar': false},
    });
    expect(capabilities.canUseOrganizerMode, isFalse);
    expect(capabilities.canUseBarMode, isFalse);
  });

  test('mode access is read from the effective capabilities endpoint', () {
    final capabilities = EffectiveCapabilities.fromJson({
      'global_roles': ['USER'],
      'structures': [
        {'organization_id': 7, 'role': 'OWNER', 'can_manage': true}
      ],
      'events': [],
      'bars': [],
      'modes': {'organizer': true, 'bar': false},
    });
    expect(capabilities.canUseOrganizerMode, isTrue);
    expect(capabilities.canUseBarMode, isFalse);
  });
}
