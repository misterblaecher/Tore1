import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/community/models/orga_invite_type.dart';

void main() {
  test('maps invite types to expected role labels', () {
    expect(orgaRoleFromInviteType('manager'), 'MANAGER');
    expect(orgaRoleFromInviteType('staff'), 'STAFF');
    expect(orgaRoleFromInviteType('follower'), 'FOLLOWER');
    expect(orgaRoleFromInviteType('unknown'), 'MEMBER');
  });
}
