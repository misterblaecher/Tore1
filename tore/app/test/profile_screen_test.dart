import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tore/core/auth/auth_session_provider.dart';
import 'package:tore/features/navigation/presentation/profile_screen.dart';
import 'package:tore/features/profile/data/profile_repository.dart';
import 'package:tore/features/profile/domain/profile_models.dart';
import 'package:tore/features/profile/presentation/profile_providers.dart';

void main() {
  const userProfile = ToreProfile(
    id: 'user-1',
    username: 'alice',
    displayName: 'Alice',
    bio: 'Bio réelle',
    privacy: ProfilePrivacy(
      profile: ProfileVisibility.private,
      photo: ProfileVisibility.private,
      bio: ProfileVisibility.private,
      affiliations: ProfileVisibility.private,
      badges: ProfileVisibility.private,
      eventHistory: ProfileVisibility.private,
      participations: ProfileVisibility.private,
      gamification: ProfileVisibility.private,
      eventHistoryOptIn: false,
      participationsOptIn: false,
      gamificationOptIn: false,
    ),
  );

  testWidgets('guest profile has no fictitious role or user identity',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) =>
            _FixedSessionNotifier(ref, const AuthSessionState.guest())),
      ],
      child: const MaterialApp(home: ProfileScreen()),
    ));
    await tester.pump();

    expect(find.text('Mode invité'), findsOneWidget);
    expect(find.textContaining('Rôle'), findsNothing);
    expect(find.textContaining('XP'), findsNothing);
    expect(find.textContaining('badge'), findsNothing);
  });

  testWidgets('connected profile shows affiliations and no gamification',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) => _FixedSessionNotifier(
            ref, const AuthSessionState.authenticated(null))),
        ownerProfileProvider
            .overrideWith((_) async => const ProfileLoadResult(userProfile)),
        affiliationsProvider.overrideWith((_) async => const [
              Affiliation(
                id: 4,
                structure: ProfileStructure(id: 7, name: 'Cercle réel'),
                role: 'BUREAU',
                status: 'ACTIVE',
                visibility: ProfileVisibility.private,
                validationSource: 'AUTHORIZED_APPROVAL',
              )
            ]),
        effectiveCapabilitiesProvider.overrideWith(
            (_) async => const EffectiveCapabilities(globalRoles: ['USER'])),
      ],
      child: const MaterialApp(home: ProfileScreen()),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Alice'), findsOneWidget);
    expect(find.text('Cercle réel'), findsOneWidget);
    expect(find.textContaining('BUREAU'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('Rôles et accès'), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    expect(find.textContaining('Aucun rôle opérationnel'), findsOneWidget);
    expect(find.textContaining('XP'), findsNothing);
    expect(find.textContaining('victoire'), findsNothing);
    expect(find.textContaining('Gamification'), findsNothing);
  });

  testWidgets('loading state is explicit', (tester) async {
    final pending = Completer<ProfileLoadResult>();
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) => _FixedSessionNotifier(
            ref, const AuthSessionState.authenticated(null))),
        ownerProfileProvider.overrideWith((_) => pending.future),
      ],
      child: const MaterialApp(home: ProfileScreen()),
    ));
    await tester.pump();
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('expired session exposes a reconnection state', (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) => _FixedSessionNotifier(
            ref,
            const AuthSessionState.unauthenticated(
                message: 'Session expirée. Connecte-toi à nouveau.'))),
      ],
      child: const MaterialApp(home: ProfileScreen()),
    ));
    await tester.pump();

    expect(
        find.text('Session expirée. Connecte-toi à nouveau.'), findsOneWidget);
    expect(find.text('Se reconnecter'), findsOneWidget);
  });

  testWidgets('an affiliation exposes navigation to its real structure',
      (tester) async {
    await tester.pumpWidget(ProviderScope(
      overrides: [
        authSessionProvider.overrideWith((ref) => _FixedSessionNotifier(
            ref, const AuthSessionState.authenticated(null))),
        ownerProfileProvider
            .overrideWith((_) async => const ProfileLoadResult(userProfile)),
        affiliationsProvider.overrideWith((_) async => const [
              Affiliation(
                id: 4,
                structure: ProfileStructure(id: 7, name: 'Cercle réel'),
                role: 'MEMBER',
                status: 'ACTIVE',
                visibility: ProfileVisibility.private,
                validationSource: 'AUTHORIZED_APPROVAL',
              )
            ]),
        effectiveCapabilitiesProvider.overrideWith(
            (_) async => const EffectiveCapabilities(globalRoles: ['USER'])),
      ],
      child: const MaterialApp(home: ProfileScreen()),
    ));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Cercle réel'), 250,
        scrollable: find.byType(Scrollable).first);
    final affiliationTile = find.ancestor(
      of: find.text('Cercle réel'),
      matching: find.byType(ListTile),
    );

    expect(affiliationTile, findsOneWidget);
    expect(
      find.descendant(
          of: affiliationTile, matching: find.byIcon(Icons.chevron_right)),
      findsOneWidget,
    );
  });
}

class _FixedSessionNotifier extends AuthSessionNotifier {
  _FixedSessionNotifier(super.ref, this.fixed) : super(autoBootstrap: false) {
    state = fixed;
  }

  final AuthSessionState fixed;
}
