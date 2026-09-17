import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'tore_mvp_app.dart';
import 'config/app_config.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    AppConfig.fromDartDefines();
  } on FormatException {
    runApp(const MaterialApp(
      home: Scaffold(body: Center(child: Padding(
        padding: EdgeInsets.all(24),
        child: Text('Cette version de TORÈ est mal configurée. Contacte l’équipe TORÈ.', textAlign: TextAlign.center),
      ))),
    ));
    return;
  }
  runApp(const ProviderScope(child: ToreMvpApp()));
}
