import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/community/presentation/orga_admin_helpers.dart';

void main() {
  test('join_mode label mapping', () {
    expect(joinModeLabel('FOLLOW_ONLY'), 'Suivi uniquement');
    expect(joinModeLabel('REQUEST_TO_JOIN'), 'Demande de rejoindre');
    expect(joinModeLabel('OPEN_MEMBERSHIP'), 'Adhésion ouverte');
  });

  test('form diff detection for settings', () {
    final payload = buildOrgaSettingsPayload(
      initial: {
        'name': 'A',
        'city': 'Liege',
        'instagram_handle': '@a',
        'description': 'desc',
        'visibility': 'PUBLIC',
        'join_mode': 'OPEN_MEMBERSHIP',
      },
      name: 'A',
      city: 'Namur',
      instagram: '@a',
      description: 'desc2',
      visibility: 'PRIVATE',
      joinMode: 'REQUEST_TO_JOIN',
    );
    expect(payload, {
      'city': 'Namur',
      'description': 'desc2',
      'visibility': 'PRIVATE',
      'join_mode': 'REQUEST_TO_JOIN',
    });
  });

  test('role change payload build', () {
    expect(buildRoleChangePayload(role: 'manager', reason: '  besoin  '), {
      'role': 'MANAGER',
      'reason': 'besoin',
    });
  });
}
