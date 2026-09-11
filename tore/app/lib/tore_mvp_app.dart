import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'core/auth/providers.dart';
import 'core/network/network_state_provider.dart';
import 'core/routing/app_deep_link_router.dart';
import 'features/auth/presentation/welcome_screen.dart';
import 'features/bars/presentation/bar_detail_screen.dart';
import 'features/bars/presentation/bars_screen.dart';
import 'features/discovery/presentation/discovery_screen.dart';
import 'features/events/presentation/event_public_screen.dart';
import 'features/menu_market/presentation/menu_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';
import 'features/operations/domain/operational_models.dart';
import 'features/operations/presentation/bar_operational_hub_screen.dart';
import 'features/operations/presentation/event_operational_hub_screen.dart';
import 'features/operations/presentation/operational_mode_switcher.dart';
import 'features/operations/presentation/operational_providers.dart';
import 'features/operations/presentation/operational_route_gate.dart';
import 'features/qr/presentation/qr_scanner_gate_screen.dart';
import 'features/qr/qr_router.dart';
import 'theme/tore_theme.dart';
import 'shared/widgets/network_banner.dart';

class ToreMvpApp extends ConsumerWidget {
  const ToreMvpApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'TORÈ',
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.dark(),
      home: const _SessionGate(),
      onGenerateRoute: (settings) {
        final rawRoute = settings.name ?? '';
        final uri = Uri.tryParse(rawRoute);
        if (uri == null) return null;
        if (uri.path == '/event-staff-invite' ||
            uri.host == 'event-staff-invite') {
          final token = uri.queryParameters['token'] ?? '';
          return MaterialPageRoute(
              settings: settings,
              builder: (_) => OperationalInvitationRouteGate(token: token));
        }
        final segments = uri.host == 'ops'
            ? <String>['ops', ...uri.pathSegments]
            : uri.pathSegments;
        if (segments.length == 3 && segments.first == 'ops') {
          final scopeId = int.tryParse(segments.last);
          final mode = segments[1] == 'event'
              ? OperationalMode.orga
              : segments[1] == 'bar'
                  ? OperationalMode.bar
                  : null;
          if (scopeId != null && mode != null) {
            return MaterialPageRoute(
                settings: settings,
                builder: (_) =>
                    ScopedOperationalRouteGate(mode: mode, scopeId: scopeId));
          }
        }

        final deepLink = const AppDeepLinkRouter().parse(rawRoute);
        if (deepLink == null) return null;
        switch (deepLink.kind) {
          case AppDeepLinkKind.event:
            return MaterialPageRoute(
              settings: settings,
              builder: (_) => EventPublicScreen(eventId: deepLink.id!),
            );
          case AppDeepLinkKind.join:
            return MaterialPageRoute(
              settings: settings,
              builder: (_) =>
                  EventPublicScreen(eventId: deepLink.id!, autoJoin: true),
            );
          case AppDeepLinkKind.bar:
            return MaterialPageRoute(
              settings: settings,
              builder: (_) => BarDetailScreen(barId: deepLink.id!),
            );
          case AppDeepLinkKind.eventMenu:
            return MaterialPageRoute(
              settings: settings,
              builder: (_) => MenuScreen(eventId: deepLink.id!),
            );
          case AppDeepLinkKind.barMenu:
            // The active mobile app has no standalone public bar-menu screen.
            // Keep the link useful and safe by landing on the canonical bar
            // detail instead of resurrecting the rebuild BAR shell.
            return MaterialPageRoute(
              settings: settings,
              builder: (_) => BarDetailScreen(barId: deepLink.id!),
            );
          case AppDeepLinkKind.qr:
            return MaterialPageRoute(
              settings: settings,
              builder: (_) => _QrDeepLinkGate(payload: deepLink.payload!),
            );
        }
      },
    );
  }
}

class _SessionGate extends ConsumerWidget {
  const _SessionGate();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authSessionProvider);
    switch (session.status) {
      case AuthStatus.unknown:
      case AuthStatus.loading:
        return const _BrandLoadingScreen();
      case AuthStatus.unauthenticated:
        return const WelcomeScreen();
      case AuthStatus.guest:
      case AuthStatus.authenticated:
        return const ToreMvpShell();
      case AuthStatus.bootstrapError:
        return _SessionErrorScreen(
          message: session.message ?? 'Session indisponible.',
          onRetry: () => ref.read(authSessionProvider.notifier).bootstrap(),
        );
    }
  }
}

class ToreMvpShell extends ConsumerStatefulWidget {
  const ToreMvpShell({super.key});

  @override
  ConsumerState<ToreMvpShell> createState() => _ToreMvpShellState();
}

class _ToreMvpShellState extends ConsumerState<ToreMvpShell>
    with WidgetsBindingObserver {
  int _selectedIndex = 0;
  Timer? _capabilityTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _capabilityTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      ref.invalidate(operationalCapabilitiesProvider);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _capabilityTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      ref.invalidate(operationalCapabilitiesProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(appContextInitProvider);
    ref.listen<NetworkSnapshot>(networkStateProvider, (previous, next) {
      if (next.state == NetworkState.online &&
          previous?.state != NetworkState.online) {
        ref.invalidate(operationalCapabilitiesProvider);
      }
    });
    ref.listen<AsyncValue<OperationalCapabilities>>(
        operationalCapabilitiesProvider, (previous, next) {
      next.whenData((capabilities) => ref
          .read(operationalSelectionProvider.notifier)
          .revalidate(capabilities));
    });
    final operational = ref.watch(operationalSelectionProvider);
    final pages = <Widget>[
      Scaffold(
        appBar: AppBar(
          titleSpacing: 16,
          title: Row(
            children: [
              Image.asset(
                'assets/branding/logo_minimal.png',
                width: 38,
                height: 38,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const Icon(Icons.bolt),
              ),
              const SizedBox(width: 10),
              const Text('TORÈ'),
            ],
          ),
          actions: [
            IconButton(
              tooltip: 'Scanner un raccourci',
              constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
              onPressed: _openScanner,
              icon: const Icon(Icons.qr_code_scanner),
            ),
          ],
        ),
        body: const DiscoveryScreen(compactHome: true),
      ),
      const DiscoveryScreen(),
      const BarsScreen(),
      const ProfileScreen(),
    ];
    final operationalBody = operational.mode == OperationalMode.orga &&
            operational.capability != null
        ? EventOperationalHubScreen(capability: operational.capability!)
        : operational.mode == OperationalMode.bar &&
                operational.capability != null
            ? BarOperationalHubScreen(capability: operational.capability!)
            : null;
    return Scaffold(
      body: Column(
        children: [
          const ToreNetworkBanner(),
          const OperationalModeSwitcher(),
          Expanded(
            child: operationalBody ??
                IndexedStack(index: _selectedIndex, children: pages),
          ),
        ],
      ),
      bottomNavigationBar: operationalBody == null
          ? NavigationBar(
              selectedIndex: _selectedIndex,
              onDestinationSelected: (index) =>
                  setState(() => _selectedIndex = index),
              destinations: const [
                NavigationDestination(
                    icon: Icon(Icons.home_outlined),
                    selectedIcon: Icon(Icons.home),
                    label: 'Accueil'),
                NavigationDestination(
                    icon: Icon(Icons.event_outlined),
                    selectedIcon: Icon(Icons.event),
                    label: 'Soirées'),
                NavigationDestination(
                    icon: Icon(Icons.local_bar_outlined),
                    selectedIcon: Icon(Icons.local_bar),
                    label: 'Bars'),
                NavigationDestination(
                    icon: Icon(Icons.person_outline),
                    selectedIcon: Icon(Icons.person),
                    label: 'Profil'),
              ],
            )
          : null,
    );
  }

  void _openScanner() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const QrScannerGateScreen()),
    );
  }
}

class _QrDeepLinkGate extends ConsumerStatefulWidget {
  const _QrDeepLinkGate({required this.payload});

  final String payload;

  @override
  ConsumerState<_QrDeepLinkGate> createState() => _QrDeepLinkGateState();
}

class _QrDeepLinkGateState extends ConsumerState<_QrDeepLinkGate> {
  bool _started = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _route());
  }

  Future<void> _route() async {
    if (_started) return;
    _started = true;
    try {
      await ref.read(qrRouterServiceProvider).route(
            context: context,
            raw: widget.payload,
          );
      if (mounted && Navigator.of(context).canPop()) {
        Navigator.of(context).pop();
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Ce lien QR TORÈ ne peut pas être ouvert.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final error = _error;
    return Scaffold(
      appBar: AppBar(title: const Text('Ouvrir TORÈ')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: error == null
              ? const CircularProgressIndicator()
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(error, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      onPressed: () => Navigator.of(context).maybePop(),
                      icon: const Icon(Icons.arrow_back),
                      label: const Text('Retour'),
                    ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _BrandLoadingScreen extends StatelessWidget {
  const _BrandLoadingScreen();

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Image.asset(
                'assets/branding/logo_minimal.png',
                width: 96,
                height: 96,
                fit: BoxFit.contain,
                errorBuilder: (_, __, ___) => const Icon(Icons.bolt, size: 64),
              ),
              const SizedBox(height: 18),
              const CircularProgressIndicator(),
            ],
          ),
        ),
      );
}

class _SessionErrorScreen extends StatelessWidget {
  const _SessionErrorScreen({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off_outlined, size: 48),
                  const SizedBox(height: 12),
                  Text(message, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: onRetry,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Réessayer'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
}
