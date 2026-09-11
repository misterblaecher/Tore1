import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../shared/utils/write_gate.dart';
import '../../../shared/utils/share_text.dart';
import '../../../shared/utils/share_intent.dart';
import '../../../core/network/network_state_provider.dart';
import '../community_models.dart';
import '../../events/presentation/event_hub_screen.dart';
import '../../events/presentation/event_manage_landing_screen.dart';
import '../../events/presentation/event_public_screen.dart';
import '../../../state.dart';
import '../../../ui/components/tore_card.dart';
import '../../../ui/components/tore_chip.dart';
import '../../../ui/components/tore_cta.dart';
import '../../../ui/components/tore_list_row.dart';
import '../../events/presentation/create_event_wizard_screen.dart';
import 'orga_events_list_screen.dart';
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
  String _idem() =>
      'orga-detail-${DateTime.now().millisecondsSinceEpoch}-${Random().nextInt(9999)}';

  bool get _isAdmin => widget.myRole == 'OWNER' || widget.myRole == 'MANAGER';
  bool _adminTab = false;

  @override
  Widget build(BuildContext context) {
    final api = ref.read(apiProvider);
    final writeAllowed = canWrite(ref, intent: WriteIntent.nonCritical);
    final writeReason =
        writeDisabledReason(ref, intent: WriteIntent.nonCritical);

    return Scaffold(
      appBar: AppBar(title: const Text('Organisation')),
      body: FutureBuilder<List<dynamic>>(
        future: Future.wait([
          api.getOrga(widget.orgId),
          api.listOrgaPublicEvents(widget.orgId),
          api.listOrgaPosts(widget.orgId),
          api.orgaMyMembership(orgId: widget.orgId),
          if (_isAdmin) api.listOrgaPrivateEvents(widget.orgId),
          if (_isAdmin) api.orgaMembers(orgId: widget.orgId),
        ]),
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting)
            return const Center(child: CircularProgressIndicator());
          if (snap.hasError || !snap.hasData)
            return const Center(child: Text('Erreur chargement orga'));
          final orga = Map<String, dynamic>.from(snap.data![0] as Map);
          final publicResult = snap.data![1] as OrgaEventsResult;
          final posts =
              ((Map<String, dynamic>.from(snap.data![2] as Map)['items']
                          as List?) ??
                      const [])
                  .cast<dynamic>();
          final myMembershipJson =
              (Map<String, dynamic>.from(snap.data![3] as Map)['membership']
                      as Map?)
                  ?.cast<String, dynamic>();
          final myMembership = myMembershipJson == null
              ? null
              : OrgaMembership.fromJson(myMembershipJson);
          final privateResult = _isAdmin && snap.data!.length > 4
              ? (snap.data![4] as OrgaEventsResult)
              : const OrgaEventsResult(
                  buckets: {},
                  nextCursor: null,
                  isCached: false,
                  lastSyncAt: null);
          final members = _isAdmin && snap.data!.length > 5
              ? ((Map<String, dynamic>.from(snap.data![5] as Map)['items']
                      as List?) ??
                  const [])
              : const [];
          final pendingCount =
              members.where((e) => (e as Map)['status'] == 'PENDING').length;

          final joinMode = parseOrgaJoinMode(orga['join_mode']?.toString());
          final status = myMembership?.status;
          final ctaLabel =
              orgaPrimaryCtaLabel(joinMode: joinMode, status: status);

          Future<void> joinOrLeave() async {
            if (status == MembershipStatus.pending ||
                status == MembershipStatus.active) {
              await api.orgaLeave(orgId: widget.orgId, idempotencyKey: _idem());
            } else {
              await api.orgaJoin(orgId: widget.orgId, idempotencyKey: _idem());
            }
            if (mounted) setState(() {});
          }

          final showingAdmin = _isAdmin && _adminTab;
          final current = showingAdmin ? privateResult : publicResult;

          return ListView(
            padding: const EdgeInsets.all(12),
            children: [
              ToreCard(
                header: Text(orga['name']?.toString() ?? 'Orga',
                    style: Theme.of(context).textTheme.titleLarge),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(orga['description']?.toString() ?? '-'),
                      const SizedBox(height: 8),
                      Wrap(spacing: 8, runSpacing: 8, children: [
                        ToreChip(
                            label: (orga['city'] ?? '-').toString(),
                            variant: ToreChipVariant.info),
                        ToreChip(
                            label: (orga['instagram_handle'] ?? '@').toString(),
                            variant: ToreChipVariant.closed),
                        if (status == MembershipStatus.pending)
                          const ToreChip(
                              label: 'Demande envoyée',
                              variant: ToreChipVariant.warn),
                        if (status == MembershipStatus.active)
                          ToreChip(
                              label:
                                  myMembership?.role == MembershipRole.follower
                                      ? 'Follower'
                                      : 'Membre',
                              variant: ToreChipVariant.ok),
                        if (current.isCached)
                          const ToreChip(
                              label: 'CACHE / OFFLINE',
                              variant: ToreChipVariant.warn),
                      ]),
                    ]),
              ),
              const SizedBox(height: 8),
              ToreCTA(
                  label: ctaLabel,
                  onPressed: writeAllowed ? joinOrLeave : null),
              if (!writeAllowed && writeReason != null)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(writeReason,
                      style: Theme.of(context).textTheme.bodySmall),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  final share = await api.getOrgaShare(widget.orgId);
                  String? shortUrl;
                  final online =
                      ref.read(networkStatusProvider) == NetworkState.online;
                  if (online) {
                    try {
                      final short = await api.createShortlink(
                          kind: 'orga_share',
                          orgaId: widget.orgId,
                          idempotencyKey: _idem());
                      shortUrl = (short['shortUrl'] ?? '').toString();
                    } catch (_) {}
                  }
                  final builder = ShareIntentBuilder(ShareIntentInput(
                    shortUrl: shortUrl,
                    openUrl: pickShareUrl(
                        webUrl: (share['webUrl'] ?? '').toString(),
                        openUrl: (share['https_link'] ?? '').toString()),
                    copyHint: kShareFallbackHintOffline,
                  ));
                  await Share.share(builder.shareText,
                      subject: 'Organisation TORÈ');
                },
                icon: const Icon(Icons.ios_share_outlined),
                label: const Text('Partager le lien'),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () async {
                  try {
                    final share = await api.getOrgaShare(widget.orgId);
                    final raw = (share['webUrl'] ?? share['https_link'] ?? '')
                        .toString()
                        .trim();
                    final uri = Uri.tryParse(raw);
                    final valid = uri != null &&
                        {'http', 'https'}.contains(uri.scheme) &&
                        uri.host.isNotEmpty;
                    if (!valid ||
                        !await launchUrl(uri!,
                            mode: LaunchMode.externalApplication)) {
                      throw StateError('forum link unavailable');
                    }
                  } catch (_) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                          content: Text(
                              'Page Forum indisponible hors connexion.')));
                    }
                  }
                },
                icon: const Icon(Icons.open_in_new),
                label: const Text('Voir la page Forum'),
              ),
              const SizedBox(height: 12),
              if (_isAdmin)
                ToreCard(
                  header: const Text('Admin'),
                  child: Column(children: [
                    ToreListRow(
                        title: 'Créer un event',
                        subtitle: 'Host = orga',
                        onTap: () async {
                          await Navigator.of(context).push(MaterialPageRoute(
                              builder: (_) => CreateEventWizardScreen(
                                  prefillHostOrgaId: widget.orgId)));
                          if (mounted) setState(() {});
                        }),
                    if (pendingCount > 0)
                      ToreListRow(
                        title: 'Demandes',
                        subtitle: '$pendingCount en attente',
                        onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => OrgaMembersAdminScreen(
                                    orgId: widget.orgId))),
                      ),
                    ToreListRow(
                        title: 'Invitations',
                        subtitle: 'Créer & révoquer',
                        onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => OrgaInvitesAdminScreen(
                                    orgId: widget.orgId)))),
                    ToreListRow(
                        title: 'Membres & rôles',
                        subtitle: '${members.length} membre(s)',
                        onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => OrgaMembersAdminScreen(
                                    orgId: widget.orgId,
                                    myRole: widget.myRole ?? 'MANAGER')))),
                    ToreListRow(
                        title: 'Paramètres',
                        subtitle: 'Visibilité, join mode, infos',
                        onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) =>
                                    OrgaSettingsScreen(orgId: widget.orgId)))),
                    ToreListRow(
                        title: 'Posts',
                        subtitle: '${posts.length} post(s)',
                        onTap: () => Navigator.of(context).push(
                            MaterialPageRoute(
                                builder: (_) => OrgaPostsScreen(
                                    orgId: widget.orgId,
                                    canModerate: _isAdmin,
                                    canPost: true)))),
                  ]),
                ),
              const SizedBox(height: 12),
              ToreCard(
                header: const Text('Events'),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (_isAdmin)
                        SegmentedButton<bool>(
                          segments: const [
                            ButtonSegment<bool>(
                                value: false, label: Text('Public')),
                            ButtonSegment<bool>(
                                value: true, label: Text('Admin')),
                          ],
                          selected: {_adminTab},
                          onSelectionChanged: (v) =>
                              setState(() => _adminTab = v.first),
                        ),
                      for (final bucket in const [
                        'TODAY',
                        'UPCOMING',
                        'PAST'
                      ]) ...[
                        Padding(
                          padding: const EdgeInsets.only(top: 10, bottom: 6),
                          child: Text(bucket,
                              style: Theme.of(context).textTheme.titleSmall),
                        ),
                        for (final event in (current.buckets[bucket] ??
                            const <MyEventSummary>[]))
                          _eventRow(event),
                      ],
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerRight,
                        child: TextButton(
                          onPressed: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                  builder: (_) => OrgaEventsListScreen(
                                      orgId: widget.orgId,
                                      isAdmin: _isAdmin,
                                      startAdmin: showingAdmin))),
                          child: const Text('Voir tout'),
                        ),
                      ),
                    ]),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _eventRow(MyEventSummary event) {
    return ToreListRow(
      title: event.name,
      subtitle: '${_dateRange(event)} • ${event.status}',
      trailing: Wrap(spacing: 6, children: [
        ToreChip(label: event.publicationStatus, variant: ToreChipVariant.info),
        ToreChip(label: event.visibility, variant: ToreChipVariant.closed),
        ToreChip(label: event.status, variant: ToreChipVariant.live),
      ]),
      onTap: () {
        if (event.joined) {
          Navigator.of(context).push(MaterialPageRoute(
              builder: (_) =>
                  EventHubScreen(eventId: event.id, eventName: event.name)));
          return;
        }
        if (event.canManage) {
          Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => EventManageLandingScreen(event: event)));
          return;
        }
        final isPublic = event.visibility.toUpperCase() == 'PUBLIC';
        if (isPublic) {
          Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => EventPublicScreen(eventId: event.id)));
          return;
        }
        Navigator.of(context).push(MaterialPageRoute(
            builder: (_) =>
                EventHubScreen(eventId: event.id, eventName: event.name)));
      },
    );
  }

  String _dateRange(MyEventSummary event) {
    final s = event.startAt;
    final e = event.endAt;
    return '${s.day.toString().padLeft(2, '0')}/${s.month.toString().padLeft(2, '0')} ${s.hour.toString().padLeft(2, '0')}:${s.minute.toString().padLeft(2, '0')} - ${e.hour.toString().padLeft(2, '0')}:${e.minute.toString().padLeft(2, '0')}';
  }
}
