import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_shell.dart';
import 'features/auth/presentation/welcome_screen.dart';
import 'theme/tore_theme.dart';
import 'state.dart';


Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: ToreApp()));
}

class ToreApp extends ConsumerWidget {
  const ToreApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final boot = ref.watch(appBootProvider);

    return MaterialApp(
      title: 'TORÈ',
      debugShowCheckedModeBanner: false,
      theme: ToreTheme.dark(),
      darkTheme: ToreTheme.dark(),
      themeMode: ThemeMode.dark,
      home: boot.when(
        loading: () => const _Splash(),
        error: (e, _) => _BootError(error: e.toString()),
        data: (state) => state.status == AppBootStatus.needsWelcome ? const WelcomeScreen() : const AppShell(),
      ),
    );
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}

class _BootError extends StatelessWidget {
  final String error;
  const _BootError({required this.error});

  @override
  Widget build(BuildContext context) {
    return _BootErrorBody(error: error);
  }
}

class _BootErrorBody extends ConsumerWidget {
  final String error;
  const _BootErrorBody({required this.error});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Erreur démarrage: $error', textAlign: TextAlign.center),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => ref.invalidate(appBootProvider),
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
