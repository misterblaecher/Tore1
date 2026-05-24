import 'package:flutter/material.dart';
import 'network_error_fallback.dart';

class OfflineFallbackScreen extends StatelessWidget {
  const OfflineFallbackScreen({
    super.key,
    required this.title,
    required this.message,
    required this.onRetry,
  });

  final String title;
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return NetworkErrorFallback(
        title: title, message: message, onRetry: onRetry);
  }
}
