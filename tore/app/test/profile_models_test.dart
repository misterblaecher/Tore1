import 'package:flutter_test/flutter_test.dart';
import 'package:tore/features/profile/domain/profile_models.dart';

void main() {
  test('owner profile parses affiliations, privacy and real history', () {
    final profile = ToreProfile.fromJson({
      'id': 'user-1',
      'username': 'alice',
      'display_name': 'Alice',
      'bio': 'Bio',
      'privacy': {
        'profile': 'TORE_USERS',
        'photo': 'PRIVATE',
        'bio': 'PUBLIC',
        'affiliations': 'PUBLIC',
        'badges': 'PRIVATE',
        'event_history': 'PRIVATE',
        'participations': 'PRIVATE',
        'gamification': 'PRIVATE',
        'event_history_opt_in': true,
      },
      'affiliations': [
        {
          'id': 4,
          'structure': {'id': 7, 'name': 'Cercle réel'},
          'role': 'BUREAU',
          'status': 'ACTIVE',
          'visibility': 'PUBLIC',
          'validation_source': 'AUTHORIZED_APPROVAL',
        }
      ],
      'event_history': [
        {'id': 8, 'name': 'Bal réel'}
      ],
    });

    expect(profile.username, 'alice');
    expect(profile.privacy!.profile, ProfileVisibility.toreUsers);
    expect(profile.privacy!.eventHistoryOptIn, isTrue);
    expect(profile.affiliations.single.role, 'BUREAU');
    expect(profile.affiliations.single.structure.id, 7);
    expect(profile.eventHistory.single['name'], 'Bal réel');
  });

  test('unknown visibility is private and missing gamification stays absent',
      () {
    final profile = ToreProfile.fromJson({
      'id': 'legacy',
      'display_name': 'Legacy',
      'privacy': {
        'profile': 'MYSTERY',
        'photo': null,
        'bio': null,
        'affiliations': null,
        'badges': null,
        'event_history': null,
        'participations': null,
        'gamification': null,
      },
    });
    expect(profile.isMinimal, isTrue);
    expect(profile.privacy!.profile, ProfileVisibility.private);
    expect(profile.eventHistory, isEmpty);
  });
}
