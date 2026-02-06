import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_exception.dart';
import '../../../core/network/error_mapper.dart';
import 'staff_providers.dart';

class StaffInviteAcceptScreen extends ConsumerStatefulWidget {
  const StaffInviteAcceptScreen({super.key, required this.eventId, required this.token});

  final int eventId;
  final String token;

  @override
  ConsumerState<StaffInviteAcceptScreen> createState() => _StaffInviteAcceptScreenState();
}

class _StaffInviteAcceptScreenState extends ConsumerState<StaffInviteAcceptScreen> {
  bool _loading = false;
  String? _error;

  Future<void> _acceptInvite() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final service = ref.read(staffServiceProvider);
      final result = await service.acceptInvite(
        eventId: widget.eventId,
        token: widget.token,
      );
      if (!mounted) return;
      if (result.ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Accès accordé (${result.roleGranted}).')),
        );
        Navigator.of(context).popUntil((route) => route.isFirst);
        return;
      }
      setState(() => _error = 'Impossible d\'accepter l\'invite.');
    } catch (e) {
      setState(() => _error = _mapInviteError(e));
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  String _mapInviteError(Object e) {
    if (e is ApiException && e.details is Map) {
      final details = e.details as Map;
      final code = details['error']?.toString();
      switch (code) {
        case 'invalid_token':
          return 'Invite invalide ou révoquée.';
        case 'expired_token':
          return 'Invite expirée.';
        case 'max_uses_reached':
          return 'Ce QR a déjà été utilisé.';
        default:
          return ErrorMapper.message(e);
      }
    }
    return ErrorMapper.message(e);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Invite staff'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Accepte l\'accès staff ENTRY pour l\'event #${widget.eventId}.',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            if (_error != null)
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: _loading ? null : _acceptInvite,
                icon: const Icon(Icons.check_circle_outline),
                label: Text(_loading ? 'Activation...' : 'Accepter l\'accès ENTRY'),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _loading ? null : () => Navigator.of(context).pop(),
                icon: const Icon(Icons.close),
                label: const Text('Annuler'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
