import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../state.dart';
import '../../../core/network/api_exception.dart';
import '../../../shared/utils/runtime_write_guard.dart';
import '../../../shared/widgets/service_limited_banner.dart';
import 'order_status_live_screen.dart';

class OrderQrScreen extends ConsumerStatefulWidget {
  const OrderQrScreen({super.key, required this.orderId});

  final int orderId;

  @override
  ConsumerState<OrderQrScreen> createState() => _OrderQrScreenState();
}

class _OrderQrScreenState extends ConsumerState<OrderQrScreen> {
  String? _qrRaw;
  DateTime? _expiresAt;
  int _remaining = 0;
  bool _loading = false;
  String? _error;
  Timer? _timer;
  DateTime? _rateLimitedUntil;
  String? _runtimeReason;

  @override
  void initState() {
    super.initState();
    unawaited(_issueQr());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _issueQr() async {
    if (_isRateLimited) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final requestKey = 'order-qr-${widget.orderId}';
      final payload = await api.issueOrderClientQr(orderId: widget.orderId, idempotencyKey: requestKey);
      final raw = (payload['qr_raw'] ?? '').toString();
      final expires = DateTime.tryParse((payload['expires_at'] ?? '').toString())?.toLocal();
      final ttl = payload['ttl_seconds'] is num ? (payload['ttl_seconds'] as num).toInt() : null;
      final expiresAt = expires ?? DateTime.now().add(Duration(seconds: ttl ?? 90));
      _startCountdown(raw, expiresAt);
    } catch (e) {
      final mapped = _mapError(e);
      setState(() {
        _error = mapped;
        _runtimeReason = normalizeRuntimeBlockReason(reason: _extractReason(e));
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  void _startCountdown(String qrRaw, DateTime expiresAt) {
    _timer?.cancel();
    setState(() {
      _qrRaw = qrRaw;
      _expiresAt = expiresAt;
      _remaining = _remainingSeconds(expiresAt);
    });
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      final left = _remainingSeconds(expiresAt);
      if (!mounted) return;
      if (left <= 0) {
        _timer?.cancel();
        setState(() {
          _remaining = 0;
          _error = 'QR expiré. Regénère un nouveau QR.';
        });
      } else {
        setState(() => _remaining = left);
      }
    });
  }

  int _remainingSeconds(DateTime expiresAt) {
    final now = DateTime.now();
    return expiresAt.difference(now).inSeconds.clamp(0, 3600);
  }

  bool get _isExpired => _remaining <= 0;

  bool get _isRateLimited =>
      _rateLimitedUntil != null && DateTime.now().isBefore(_rateLimitedUntil!);

  int get _cooldownLeft {
    if (_rateLimitedUntil == null) return 0;
    return _rateLimitedUntil!.difference(DateTime.now()).inSeconds.clamp(0, 120);
  }

  String _mapError(Object e) {
    String? reason;
    String message = 'Erreur réseau. Réessaie.';

    if (e is ApiException) {
      message = e.message;
      final details = e.details;
      if (details is Map && details['detail'] is Map) {
        reason = (details['detail'] as Map)['reason']?.toString();
      }
    } else if (e is DioException) {
      message = e.message ?? message;
      final data = e.response?.data;
      if (data is Map && data['detail'] is Map) {
        reason = (data['detail'] as Map)['reason']?.toString();
      }
      final wrapped = e.error;
      if (wrapped is ApiException) {
        message = wrapped.message;
      }
    }

    if (reason == 'rate_limited') {
      _rateLimitedUntil = DateTime.now().add(const Duration(seconds: 8));
      return 'Trop de requêtes. Attends quelques secondes.';
    }
    if (reason == 'event_paused' || reason == 'module_off') {
      return 'Service en pause.';
    }
    if (reason == 'read_only' || reason == 'frozen' || reason == 'closed' || reason == 'event_closed') {
      return writeBlockedReasonMessage(normalizeRuntimeBlockReason(reason: reason));
    }
    if (reason == 'revoked') {
      return 'Service indisponible pour le moment.';
    }

    final lower = message.toLowerCase();
    if (lower.contains('expired') || lower.contains('invalid')) {
      return 'QR expiré.';
    }
    if (lower.contains('rate')) {
      _rateLimitedUntil = DateTime.now().add(const Duration(seconds: 8));
      return 'Trop de requêtes. Attends quelques secondes.';
    }
    return message;
  }

  String? _extractReason(Object e) {
    if (e is ApiException) {
      final details = e.details;
      if (details is Map && details['detail'] is Map) {
        return (details['detail'] as Map)['reason']?.toString();
      }
    }
    if (e is DioException) {
      final data = e.response?.data;
      if (data is Map && data['detail'] is Map) {
        return (data['detail'] as Map)['reason']?.toString();
      }
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final accent = _isExpired ? Colors.redAccent : Colors.greenAccent;
    return Scaffold(
      appBar: AppBar(title: const Text('Order QR')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Présente ce QR au bar',
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Commande #${widget.orderId}',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.white.withOpacity(0.8)),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: Center(
                child: _qrRaw == null
                    ? (_loading
                        ? const CircularProgressIndicator()
                        : const Text('QR indisponible'))
                    : Opacity(
                        opacity: _isExpired ? 0.35 : 1,
                        child: Container(
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                          ),
                          child: QrImageView(
                            data: _qrRaw!,
                            size: 280,
                            backgroundColor: Colors.white,
                          ),
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0xFF111827),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: accent.withOpacity(0.55)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Expire dans'),
                  Text(
                    _isExpired ? 'Expiré' : '${_remaining}s',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: accent,
                    ),
                  ),
                ],
              ),
            ),
            if (_expiresAt != null) ...[
              const SizedBox(height: 6),
              Text(
                'Expire à ${_expiresAt!.hour.toString().padLeft(2, '0')}:${_expiresAt!.minute.toString().padLeft(2, '0')}:${_expiresAt!.second.toString().padLeft(2, '0')}',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white.withOpacity(0.75), fontSize: 12),
              ),
            ],
            if (_error != null) ...[
              const SizedBox(height: 10),
              _runtimeReason != null
                  ? ServiceLimitedBanner(message: writeBlockedReasonMessage(_runtimeReason))
                  : Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFF7F1D1D),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text(_error!),
                    ),
            ],
            const SizedBox(height: 12),

            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _qrRaw == null
                  ? null
                  : () async {
                      await Clipboard.setData(ClipboardData(text: _qrRaw!));
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Lien QR copié')),
                        );
                      }
                    },
              icon: const Icon(Icons.copy_all_outlined),
              label: const Text('Copier le deeplink'),
            ),

            OutlinedButton.icon(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => OrderStatusLiveScreen(orderId: widget.orderId)),
                );
              },
              icon: const Icon(Icons.track_changes_outlined),
              label: const Text('Suivi live'),
            ),
            ElevatedButton.icon(
              onPressed: (_loading || _isRateLimited) ? null : () => _issueQr(),
              icon: const Icon(Icons.refresh),
              label: Text(_isRateLimited ? 'Réessaie dans ${_cooldownLeft}s' : 'Regénérer'),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }
}
