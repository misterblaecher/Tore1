import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:tore/features/bars/presentation/bar_events_screen.dart';
import 'package:tore/features/bars/presentation/bars_screen.dart';

import 'app_shell.dart';
import 'features/auth/presentation/welcome_screen.dart';
import 'features/community/presentation/orga_detail_screen.dart';
import 'features/community/presentation/orga_invite_join_screen.dart';
import 'features/qr/presentation/join_event_screen.dart';
import 'features/events/presentation/staff_invite_join_screen.dart';
import 'features/events/presentation/staff_backup_join_screen.dart';
import 'package:tore/theme/theme.dart';
import 'state.dart';
import 'core/network/providers.dart';
import 'core/auth/providers.dart';
import 'core/perf/perf_overlay.dart';
import 'core/perf/perf_tracer.dart';
import 'config/app_config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final appConfig = AppConfig.fromDartDefines();
  debugPrint('[Boot] TORE environment=${appConfig.environmentName} API base URL=${appConfig.apiBaseUrl}');

  runApp(
    ProviderScope(
      overrides: [appConfigProvider.overrideWithValue(appConfig)],
      child: const ToreApp(),
    ),
  );
}

class ToreApp extends ConsumerWidget {
  const ToreApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      title: 'TORÈ',
      debugShowCheckedModeBanner: false,
      theme: buildToreThemeData(ToreThemeMode.ritual),
      darkTheme: buildToreThemeData(ToreThemeMode.ritual),
      themeMode: ThemeMode.dark,
      routes: {
        '/bars': (_) => const BarsScreen(),
      },
      builder: (context, child) {
        return Stack(
          children: [
            if (child != null) child,
            const PerfOverlay(),
          ],
        );
      },
      onGenerateRoute: (settings) {
        final name = settings.name;
        if (name == null) return null;
        final uri = Uri.tryParse(name);
        if (uri != null) {
          final isOpen = (uri.scheme == 'tore' && uri.host == 'open') ||
              (uri.scheme == 'https' && uri.host == 'app.tore.be' && uri.path == '/open');
          if (isOpen) {
            final type = (uri.queryParameters['type'] ?? '').toLowerCase();
            final id = int.tryParse(uri.queryParameters['id'] ?? uri.queryParameters['eventId'] ?? uri.queryParameters['event_id'] ?? uri.queryParameters['org_id'] ?? '');
            final code = (uri.queryParameters['code'] ?? '').trim();
            if (type == 'event') {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => JoinEventScreen(prefillEventId: id),
              );
            }
            if (type == 'join') {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => JoinEventScreen(prefillCode: code, autoJoinCode: code.isNotEmpty),
              );
            }
            if (type == 'orga' && id != null) {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => OrgaDetailScreen(orgId: id),
              );
            }
            if (type == 'staff_invite') {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => StaffInviteJoinScreen(code: code),
              );
            }
            if (type == 'staff_backup') {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => StaffBackupJoinScreen(prefillEventId: id, prefillCode: code),
              );
            }
            if (type == 'orga_invite') {
              return MaterialPageRoute(
                settings: settings,
                builder: (_) => OrgaInviteJoinScreen(code: code),
              );
            }
          }
        }
        final segments = uri?.pathSegments ?? const <String>[];
        if (segments.length == 3 &&
            segments[0] == 'bars' &&
            segments[2] == 'events') {
          final barId = int.tryParse(segments[1]);
          if (barId == null) return null;
          final barName = settings.arguments is String ? settings.arguments! as String : 'Bar #$barId';
          return MaterialPageRoute(
            settings: settings,
            builder: (_) => BarEventsScreen(barId: barId, barName: barName),
          );
        }
        return null;
      },
      home: const _BootEntry(),
    );
  }
}

class _BootEntry extends ConsumerStatefulWidget {
  const _BootEntry();

  @override
  ConsumerState<_BootEntry> createState() => _BootEntryState();
}

class _BootEntryState extends ConsumerState<_BootEntry> {
  bool _continueReadOnly = false;

  @override
  Widget build(BuildContext context) {
    final boot = ref.watch(appBootProvider);

    if (boot.bootStatus == BootStatus.bootLoading) {
      return const _BootSplash(
        title: 'TORÈ',
        status: 'Connexion…',
      );
    }

    if (boot.bootStatus == BootStatus.bootErrorRetry) {
      return _BootSplash(
        title: 'TORÈ',
        status: 'Erreur de démarrage',
        details: boot.errorMessage,
        onRetry: () => ref.read(appBootProvider.notifier).bootstrap(),
        onContinueReadOnly: () => setState(() => _continueReadOnly = true),
      );
    }

    if (boot.bootStatus == BootStatus.bootOfflineReadOnly && !_continueReadOnly) {
      return _BootSplash(
        title: 'TORÈ',
        status: 'Mode lecture (réseau indisponible)',
        details: 'Les actions d’écriture sont bloquées tant que le réseau est indisponible.',
        onRetry: () => ref.read(appBootProvider.notifier).bootstrap(),
        onContinueReadOnly: () => setState(() => _continueReadOnly = true),
      );
    }

    final authSession = ref.watch(authSessionProvider);
    if (authSession.status == AuthStatus.loading) {
      return const _BootSplash(title: 'TORÈ', status: 'Session…');
    }
    return authSession.isAuthed || authSession.isGuest ? const AppShell() : const WelcomeScreen();
  }
}

class _BootSplash extends ConsumerWidget {
  const _BootSplash({
    required this.title,
    required this.status,
    this.details,
    this.onRetry,
    this.onContinueReadOnly,
  });

  final String title;
  final String status;
  final String? details;
  final VoidCallback? onRetry;
  final VoidCallback? onContinueReadOnly;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              GestureDetector(
                onLongPress: () {
                  final isDev = ref.read(appConfigProvider).environmentName == 'dev';
                  if (!isDev) return;
                  final enabled = ref.read(perfOverlayEnabledProvider);
                  ref.read(perfOverlayEnabledProvider.notifier).state = !enabled;
                },
                child: Text(title, style: Theme.of(context).textTheme.headlineMedium),
              ),
              const SizedBox(height: 16),
              if (onRetry == null) ...[
                const CircularProgressIndicator(),
                const SizedBox(height: 12),
              ],
              Text(status, textAlign: TextAlign.center),
              if (details != null) ...[
                const SizedBox(height: 8),
                Text(details!, textAlign: TextAlign.center),
              ],
              if (onRetry != null) ...[
                const SizedBox(height: 14),
                FilledButton(onPressed: onRetry, child: const Text('Retry')),
              ],
              if (onContinueReadOnly != null) ...[
                const SizedBox(height: 8),
                TextButton(
                  onPressed: onContinueReadOnly,
                  child: const Text('Continuer en mode lecture'),
                ),
              ]
            ],
          ),
        ),
      ),
    );
  }
}
