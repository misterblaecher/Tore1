import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../core/network/error_mapper.dart';
import '../../../shared/models/event_staff.dart';
import '../../../shared/models/staff_invite.dart';
import 'staff_providers.dart';

class StaffManagementScreen extends ConsumerStatefulWidget {
  const StaffManagementScreen({super.key, required this.eventId});

  final int eventId;

  @override
  ConsumerState<StaffManagementScreen> createState() => _StaffManagementScreenState();
}

class _StaffManagementScreenState extends ConsumerState<StaffManagementScreen> {
  StaffInvite? _invite;
  bool _loadingInvite = false;

  Future<void> _createInvite() async {
    setState(() => _loadingInvite = true);
    try {
      final service = ref.read(staffServiceProvider);
      final invite = await service.createInvite(eventId: widget.eventId);
      setState(() => _invite = invite);
      ref.invalidate(eventStaffProvider(widget.eventId));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invite ENTRY créée.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ErrorMapper.message(e))),
      );
    } finally {
      if (mounted) {
        setState(() => _loadingInvite = false);
      }
    }
  }

  Future<void> _revokeStaff(EventStaffMember member) async {
    try {
      final service = ref.read(staffServiceProvider);
      await service.revokeStaff(eventId: widget.eventId, userId: member.userId);
      ref.invalidate(eventStaffProvider(widget.eventId));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Accès staff révoqué.')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(ErrorMapper.message(e))),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final staffAsync = ref.watch(eventStaffProvider(widget.eventId));
    final invite = _invite;

    return Scaffold(
      appBar: AppBar(
        title: Text('Staff • Event #${widget.eventId}'),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(eventStaffProvider(widget.eventId));
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _InviteCard(
              invite: invite,
              loading: _loadingInvite,
              onCreate: _createInvite,
            ),
            const SizedBox(height: 20),
            Text('Staff', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            staffAsync.when(
              data: (staff) => _StaffList(
                staff: staff,
                onRevoke: _revokeStaff,
              ),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (err, _) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text('Impossible de charger le staff. ${ErrorMapper.message(err)}'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _InviteCard extends StatelessWidget {
  const _InviteCard({
    required this.invite,
    required this.loading,
    required this.onCreate,
  });

  final StaffInvite? invite;
  final bool loading;
  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) {
    final hasInvite = invite != null && invite!.inviteQr.isNotEmpty;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Invite staff ENTRY',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                ElevatedButton.icon(
                  onPressed: loading ? null : onCreate,
                  icon: const Icon(Icons.add_circle_outline),
                  label: const Text('Créer'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (!hasInvite)
              const Text('Génère un QR pour inviter un staff (1 usage).')
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: QrImageView(
                        data: invite!.inviteQr,
                        size: 180,
                        backgroundColor: Colors.white,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SelectableText(
                    invite!.inviteQr,
                    style: const TextStyle(fontSize: 13),
                  ),
                  const SizedBox(height: 8),
                  if (invite!.expiresAt != null)
                    Text('Expire le ${invite!.expiresAt}'),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    children: [
                      TextButton.icon(
                        onPressed: () async {
                          await Clipboard.setData(
                            ClipboardData(text: invite!.inviteQr),
                          );
                          if (!context.mounted) return;
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Lien copié.')),
                          );
                        },
                        icon: const Icon(Icons.copy_outlined),
                        label: const Text('Copier'),
                      ),
                      TextButton.icon(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Partage: bientôt.')),
                          );
                        },
                        icon: const Icon(Icons.share_outlined),
                        label: const Text('Partager'),
                      ),
                    ],
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _StaffList extends StatelessWidget {
  const _StaffList({
    required this.staff,
    required this.onRevoke,
  });

  final List<EventStaffMember> staff;
  final ValueChanged<EventStaffMember> onRevoke;

  @override
  Widget build(BuildContext context) {
    if (staff.isEmpty) {
      return const Text('Aucun staff pour le moment.');
    }

    return Column(
      children: staff.map((member) {
        final status = member.isActive ? 'Actif' : 'Révoqué';
        final title = member.displayName?.isNotEmpty == true
            ? member.displayName!
            : member.userId;

        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            title: Text(title),
            subtitle: Text('${member.role.toUpperCase()} • $status'),
            trailing: member.isActive
                ? TextButton(
                    onPressed: () => onRevoke(member),
                    child: const Text('Révoquer'),
                  )
                : const Text('Inactif'),
          ),
        );
      }).toList(),
    );
  }
}
