import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/utils/write_gate.dart';
import '../community_models.dart';
import '../../events/presentation/event_manage_landing_screen.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_cta.dart';
import '../../../ui/components/tore_list_row.dart';
import '../../events/presentation/create_event_wizard_screen.dart';
import 'orga_posts_screen.dart';

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
    return Scaffold(
      appBar: AppBar(title: const Text('Organisation')),
      body: FutureBuilder<List<dynamic>>(
        future: Future.wait([api.getOrga(widget.orgId), api.listOrgaPublicEvents(widget.orgId), api.listOrgaPosts(widget.orgId), if (_isAdmin) api.orgaPrivateEvents(widget.orgId)]),
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
          if (snap.hasError || !snap.hasData) return const Center(child: Text('Erreur chargement orga'));
          final orga = Map<String, dynamic>.from(snap.data![0] as Map);
          final events = ((Map<String, dynamic>.from(snap.data![1] as Map)['items'] as List?) ?? const []).cast<dynamic>();
          final posts = ((Map<String, dynamic>.from(snap.data![2] as Map)['items'] as List?) ?? const []).cast<dynamic>();
          final privateBuckets = _isAdmin && snap.data!.length > 3 ? (snap.data![3] as Map<String, List<MyEventSummary>>) : <String, List<MyEventSummary>>{};

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
                  ]),
                ]),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  final share = await api.getOrgaShare(widget.orgId);
                  final text = '${share['webUrl'] ?? ''}
${share['deeplink'] ?? ''}';
                  await Clipboard.setData(ClipboardData(text: text));
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Lien orga copié')));
                },
                icon: const Icon(Icons.ios_share_outlined),
                label: const Text('Partager le lien'),
              ),
              const SizedBox(height: 12),
              if (!_isAdmin)
                Row(children: [
                  Expanded(child: ToreCTA(label: 'Follow', onPressed: canWrite(ref, intent: WriteIntent.nonCritical) ? () async { await api.followOrga(orgId: widget.orgId, idempotencyKey: _idem()); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Follow OK'))); } : null)),
                  const SizedBox(width: 8),
                  Expanded(child: ToreCTA(label: 'Unfollow', style: ToreCTAStyle.secondary, onPressed: canWrite(ref, intent: WriteIntent.nonCritical) ? () async { await api.unfollowOrga(orgId: widget.orgId, idempotencyKey: _idem()); if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Unfollow OK'))); } : null)),
                ]),
              if (_isAdmin)
                ToreCard(
                  header: const Text('Admin'),
                  child: Column(children: [
                    ToreListRow(title: 'Créer un event', subtitle: 'Host = orga', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CreateEventWizardScreen(prefillOrga: orga)))),
                    ToreListRow(title: 'Inviter', subtitle: 'QR + lien + copier', onTap: () async {
                      final invite = await api.getOrgaInvite(widget.orgId);
                      final code = (invite['invite_code'] ?? '').toString();
                      final link = (invite['https_link'] ?? '').toString();
                      await Clipboard.setData(ClipboardData(text: '$code\n$link'));
                      if (!mounted) return;
                      showDialog(context: context, builder: (_) => AlertDialog(title: const Text('Invitation'), content: Text('Code: $code\nLien: $link\nQR payload: ${invite['qr_payload']}')));
                    }),
                    ToreListRow(title: 'Posts', subtitle: '${posts.length} post(s)', onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => OrgaPostsScreen(orgId: widget.orgId, canModerate: _isAdmin, canPost: true)))),
                  ]),
                ),
              const SizedBox(height: 12),
              ToreCard(
                header: const Text('Events publics'),
                child: Column(children: [for (final e in events) ToreListRow(title: (e['name'] ?? 'Event').toString(), subtitle: '${e['bucket'] ?? ''} • ${e['eventState'] ?? ''}')]),
              ),
              const SizedBox(height: 12),
              if (_isAdmin)
                ToreCard(
                  header: const Text('Events (privés)'),
                  child: Column(
                    children: [
                      for (final bucket in const ['LIVE', 'TODAY', 'UPCOMING', 'PAST'])
                        ...[
                          if ((privateBuckets[bucket] ?? const <MyEventSummary>[]).isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 8, bottom: 4),
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: Text(bucket, style: const TextStyle(fontWeight: FontWeight.w700)),
                              ),
                            ),
                          for (final event in (privateBuckets[bucket] ?? const <MyEventSummary>[]))
                            ToreListRow(
                              title: event.name,
                              subtitle: '${event.visibility} • ${event.status} • ${event.roleForMe}',
                              trailing: TextButton(
                                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => EventManageLandingScreen(event: event))),
                                child: const Text('Reprendre'),
                              ),
                            ),
                        ],
                    ],
                  ),
                ),
              if (_isAdmin) const SizedBox(height: 12),
              ToreCard(
                header: const Text('Posts'),
                child: Column(children: [for (final p in posts.take(3)) ToreListRow(title: (p as Map)['text']?.toString() ?? '-', subtitle: (p['author_user_id'] ?? '').toString())]),
              ),
            ],
          );
        },
      ),
    );
  }
}
