import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app_context/app_context.dart';
import 'core/auth/providers.dart';
import 'features/auth/presentation/welcome_screen.dart';
import 'features/bars/presentation/bars_screen.dart';
import 'features/discovery/presentation/discovery_screen.dart';
import 'features/navigation/presentation/profile_screen.dart';
import 'features/qr/presentation/qr_scanner_gate_screen.dart';
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

class _ToreMvpShellState extends ConsumerState<ToreMvpShell> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    ref.watch(appContextInitProvider);
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
    return Scaffold(
      body: Column(
        children: [
          const ToreNetworkBanner(),
          Expanded(
            child: IndexedStack(index: _selectedIndex, children: pages),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
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
      ),
    );
  }

  void _openScanner() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const QrScannerGateScreen()),
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
