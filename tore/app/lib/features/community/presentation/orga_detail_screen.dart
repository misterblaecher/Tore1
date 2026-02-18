import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../community_models.dart';
import '../../events/presentation/event_manage_landing_screen.dart';
import '../../events/presentation/event_share_pack_screen.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_cta.dart';
import '../../../ui/components/tore_list_row.dart';
import '../../events/presentation/create_event_wizard_screen.dart';
import 'orga_invites_admin_screen.dart';
import 'orga_members_admin_screen.dart';
import 'orga_posts_screen.dart';
import 'orga_settings_screen.dart';

class OrgaDetailScreen extends ConsumerStatefulWidget {
  const OrgaDetailScreen({super.key, required this.orgId, this.myRole});

  final int orgId;
  final String? myRole;

  @override
  ConsumerState<OrgaDetailScreen> createState() => _OrgaDetailScreenState();
}

class _OrgaDetailScreenState extends ConsumerState<OrgaDetailScreen> {
  String _idem() => 'orga-detail-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  bool get _isAdmin => widget.myRole == 'OWNER' || widget.myRole == 'MANAGER';

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    final writeAllowed = canWrite(ref, intent: WriteIntent.nonCritical);
    final writeReason = writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    return Scaffold(
      appBar: AppBar(title: const Text('Organisation')),
      body: FutureBuilder<List<dynamic>>(
        future: Future.wait([
          api.getOrga(widget.orgId),
          api.listOrgaPublicEvents(widget.orgId),
          api.listOrgaPosts(widget.orgId),
          api.orgaMyMembership(orgId: widget.orgId),
          if (_isAdmin) api.orgaPrivateEvents(widget.orgId),
          if (_isAdmin) api.orgaMembers(orgId: widget.orgId),
        ]),
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (snap.hasError || !snap.hasData) return const Center(child: Text('Erreur chargement orga'));
          final orga = Map<String, dynamic>.from(snap.data![0] as Map);
          final events = ((Map<String, dynamic>.from(snap.data![1] as Map)['items'] as List?) ?? const []).cast<dynamic>();
          final posts = ((Map<String, dynamic>.from(snap.data![2] as Map)['items'] as List?) ?? const []).cast<dynamic>();
          final myMembershipJson = (Map<String, dynamic>.from(snap.data![3] as Map)['membership'] as Map?)?.cast<String, dynamic>();
          final myMembership = myMembershipJson == null ? null : OrgaMembership.fromJson(myMembershipJson);
          final privateBuckets = _isAdmin && snap.data!.length > 4 ? (snap.data![4] as Map<String, List<MyEventSummary>>) : <String, List<MyEventSummary>>{};
          final members = _isAdmin && snap.data!.length > 5 ? ((Map<String, dynamic>.from(snap.data![5] as Map)['items'] as List?) ?? const []) : const [];
          final pendingCount = members.where((e) => (e as Map)['status'] == 'PENDING').length;

          final joinMode = parseOrgaJoinMode(orga['join_mode']?.toString());
          final status = myMembership?.status;
          final ctaLabel = orgaPrimaryCtaLabel(joinMode: joinMode, status: status);

          Future<void> joinOrLeave() async {
            if (status == MembershipStatus.pending || status == MembershipStatus.active) {
              await api.orgaLeave(orgId: widget.orgId, idempotencyKey: _idem());
            } else {
              await api.orgaJoin(orgId: widget.orgId, idempotencyKey: _idem());
            }
            if (mounted) setState(() {});
          }

          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              ToreCard(
                header: Text(orga['name']?.toString() ?? 'Orga', style: Theme.of(context).textTheme.titleLarge),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(orga['description']?.toString() ?? '-'),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    ToreChip(label: (orga['city'] ?? '-').toString(), variant: ToreChipVariant.info),
                    ToreChip(label: (orga['instagram_handle'] ?? '@').toString(), variant: ToreChipVariant.closed),
                    if (status == MembershipStatus.pending) const ToreChip(label: 'Demande envoyée', variant: ToreChipVariant.warning),
                    if (status == MembershipStatus.active) ToreChip(label: myMembership?.role == MembershipRole.follower ? 'Follower' : 'Membre', variant: ToreChipVariant.success),
                  ]),
                ]),
              ),
              const SizedBox(height: 8),
              ToreCTA(label: ctaLabel, onPressed: writeAllowed ? joinOrLeave : null),
              if (!writeAllowed && writeReason != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(writeReason, style: Theme.of(context).textTheme.bodySmall),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  final share = await api.getOrgaShare(widget.orgId);
                  final text = '${share['webUrl'] ?? ''}\n${share['deeplink'] ?? ''}';
                  await Clipboard.setData(ClipboardData(text: text));
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Lien orga copié')));
                },
                icon: const Icon(Icons.ios_share_outlined),
                label: const Text('Partager le lien'),
              ),
              const SizedBox(height: 12),
              if (_isAdmin)
                ToreCard(
                  header: const Text('Admin'),
                  child: Column(children: [
                    ToreListRow(title: 'Créer un event', subtitle: 'Host = orga', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CreateEventWizardScreen(prefillOrga: orga)))),
                    if (pendingCount > 0)
                      ToreListRow(
                        title: 'Demandes',
                        subtitle: '$pendingCount en attente',
                        onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaMembersAdminScreen(orgId: widget.orgId))),
                      ),
                    ToreListRow(title: 'Invitations', subtitle: 'Créer & révoquer', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaInvitesAdminScreen(orgId: widget.orgId)))),
                    ToreListRow(title: 'Membres & rôles', subtitle: '${members.length} membre(s)', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaMembersAdminScreen(orgId: widget.orgId, myRole: widget.myRole ?? 'MANAGER')))),
                    ToreListRow(title: 'Paramètres', subtitle: 'Visibilité, join mode, infos', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaSettingsScreen(orgId: widget.orgId)))),
                    ToreListRow(title: 'Posts', subtitle: '${posts.length} post(s)', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaPostsScreen(orgId: widget.orgId, canModerate: _isAdmin, canPost: true)))),
                  ]),
                ),
              const SizedBox(height: 12),
              ToreCard(header: const Text('Events publics'), child: Column(children: [for (final e in events) ToreListRow(title: (e['name'] ?? 'Event').toString(), subtitle: '${e['bucket'] ?? ''} • ${e['eventState'] ?? ''}')])),
              if (_isAdmin) const SizedBox(height: 12),
              if (_isAdmin)
                ToreCard(
                  header: const Text('Events (privés)'),
                  child: Column(children: [
                    for (final bucket in const ['LIVE', 'TODAY', 'UPCOMING', 'PAST'])
                      ...[
                        for (final event in (privateBuckets[bucket] ?? const <MyEventSummary>[]))
                          ToreListRow(
                            title: event.name,
                            subtitle: '${event.visibility} • ${event.status} • ${event.roleForMe}',
                            trailing: Wrap(spacing: 4, children: [
                              TextButton(onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventManageLandingScreen(event: event))), child: const Text('Reprendre')),
                              if (event.canManage) TextButton(onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventSharePackScreen(eventId: event.id))), child: const Text('Share pack')),
                            ]),
                          ),
                      ]
                  ]),
                ),
            ],
          );
        },
      ),
    );
  }
}
