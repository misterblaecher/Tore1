import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/community/community_models.dart';

void main() {
  test('parse join mode and membership status', () {
    expect(parseOrgaJoinMode('FOLLOW_ONLY'), OrgaJoinMode.followOnly);
    expect(parseOrgaJoinMode('OPEN_MEMBERSHIP'), OrgaJoinMode.openMembership);
    expect(parseOrgaJoinMode('REQUEST_TO_JOIN'), OrgaJoinMode.requestToJoin);
    expect(parseMembershipStatus('PENDING'), MembershipStatus.pending);
    expect(parseMembershipStatus('ACTIVE'), MembershipStatus.active);
  });

  test('cta label mapping', () {
    expect(orgaPrimaryCtaLabel(joinMode: OrgaJoinMode.followOnly, status: null),
        'Suivre');
    expect(
        orgaPrimaryCtaLabel(
            joinMode: OrgaJoinMode.openMembership, status: null),
        'Rejoindre');
    expect(
        orgaPrimaryCtaLabel(joinMode: OrgaJoinMode.requestToJoin, status: null),
        'Demander à rejoindre');
    expect(
        orgaPrimaryCtaLabel(
            joinMode: OrgaJoinMode.openMembership,
            status: MembershipStatus.pending),
        'Demande envoyée');
    expect(
        orgaPrimaryCtaLabel(
            joinMode: OrgaJoinMode.openMembership,
            status: MembershipStatus.active),
        'Quitter');
  });
}
