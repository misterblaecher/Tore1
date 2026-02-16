import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class WriteGateResult {
  const WriteGateResult({required this.allowed});

  final bool allowed;
}

class WriteGate {
  const WriteGate._();

  static Future<WriteGateResult> guard({
    required BuildContext context,
    required WidgetRef ref,
    required int eventId,
    required bool critical,
    required String action,
  }) async {
    return const WriteGateResult(allowed: true);
  }
}
