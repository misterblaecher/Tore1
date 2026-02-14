import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_shell.dart';
import 'features/auth/presentation/welcome_screen.dart';
import 'package:tore/theme/theme.dart';
import 'state.dart';


Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: ToreApp()));
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

    return boot.status == AppBootStatus.needsWelcome ? const WelcomeScreen() : const AppShell();
  }
}

class _BootSplash extends StatelessWidget {
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
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
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
