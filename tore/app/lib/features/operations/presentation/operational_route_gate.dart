import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_session_provider.dart';
import '../../auth/presentation/welcome_screen.dart';
import '../domain/operational_models.dart';
import 'bar_operational_hub_screen.dart';
import 'event_operational_hub_screen.dart';
import 'invitation_center_screen.dart';
import 'operational_providers.dart';

class OperationalInvitationRouteGate extends ConsumerWidget {
  const OperationalInvitationRouteGate({super.key, required this.token});

  final String token;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authSessionProvider);
    if (session.status == AuthStatus.loading ||
        session.status == AuthStatus.unknown) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!session.isAuthed) return const WelcomeScreen();
    return InvitationCenterScreen(initialToken: token);
  }
}

class ScopedOperationalRouteGate extends ConsumerWidget {
  const ScopedOperationalRouteGate({
    super.key,
    required this.mode,
    required this.scopeId,
  });

  final OperationalMode mode;
  final int scopeId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authSessionProvider);
    if (session.status == AuthStatus.loading ||
        session.status == AuthStatus.unknown) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!session.isAuthed) return const WelcomeScreen();
    return ref.watch(operationalCapabilitiesProvider).when(
          loading: () =>
              const Scaffold(body: Center(child: CircularProgressIndicator())),
          error: (_, __) => const _RouteDenied(),
          data: (capabilities) {
            final action = mode == OperationalMode.orga
                ? 'event.view_ops'
                : 'bar.view_ops';
            if (!OperationalGuard.allowsDeepLink(
                capabilities: capabilities,
                mode: mode,
                scopeId: scopeId,
                action: action)) {
              return const _RouteDenied();
            }
            final candidates = mode == OperationalMode.orga
                ? capabilities.events
                : capabilities.bars;
            final capability = candidates.firstWhere((item) =>
                (mode == OperationalMode.orga ? item.eventId : item.barId) ==
                scopeId);
            Future.microtask(() => ref
                .read(operationalSelectionProvider.notifier)
                .selectScoped(mode, capability, capabilities));
            return Scaffold(
              appBar: AppBar(title: Text(capability.displayName)),
              body: mode == OperationalMode.orga
                  ? EventOperationalHubScreen(capability: capability)
                  : BarOperationalHubScreen(capability: capability),
            );
          },
        );
  }
}

class _RouteDenied extends StatelessWidget {
  const _RouteDenied();

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Accès opérationnel')),
        body: const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'Accès refusé ou expiré. Les autorisations ont été revérifiées.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      );
}
