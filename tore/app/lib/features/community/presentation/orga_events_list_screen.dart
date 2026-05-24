import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state.dart';
import '../../events/presentation/event_hub_screen.dart';
import '../../events/presentation/event_manage_landing_screen.dart';
import '../community_models.dart';

class OrgaEventsListScreen extends ConsumerStatefulWidget {
  const OrgaEventsListScreen(
      {super.key,
      required this.orgId,
      required this.isAdmin,
      this.startAdmin = false});

  final int orgId;
  final bool isAdmin;
  final bool startAdmin;

  @override
  ConsumerState<OrgaEventsListScreen> createState() =>
      _OrgaEventsListScreenState();
}

class _OrgaEventsListScreenState extends ConsumerState<OrgaEventsListScreen> {
  bool _admin = false;
  String _query = '';
  OrgaEventsResult? _result;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _admin = widget.startAdmin;
    _load();
  }

  Future<void> _load({String? cursor}) async {
    setState(() => _loading = true);
    try {
      final api = ref.read(apiProvider);
      final next = _admin && widget.isAdmin
          ? await api.listOrgaPrivateEvents(widget.orgId, cursor: cursor)
          : await api.listOrgaPublicEvents(widget.orgId);
      if (!mounted) return;
      if (cursor != null && _result != null) {
        final merged = <String, List<OrgaEventSummary>>{};
        for (final k in const ['LIVE', 'TODAY', 'UPCOMING', 'PAST']) {
          merged[k] = [...?_result!.buckets[k], ...?next.buckets[k]];
        }
        _result = OrgaEventsResult(
            buckets: merged,
            nextCursor: next.nextCursor,
            isCached: next.isCached,
            lastSyncAt: next.lastSyncAt);
      } else {
        _result = next;
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    final all = [
      for (final b in const ['LIVE', 'TODAY', 'UPCOMING', 'PAST'])
        ...?(result?.buckets[b])
    ]
        .where((e) => e.name.toLowerCase().contains(_query.toLowerCase()))
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Tous les events')),
      body: Column(
        children: [
          if (widget.isAdmin)
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('Public')),
                ButtonSegment(value: true, label: Text('Admin'))
              ],
              selected: {_admin},
              onSelectionChanged: (v) {
                setState(() => _admin = v.first);
                _load();
              },
            ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: TextField(
              decoration: const InputDecoration(
                  prefixIcon: Icon(Icons.search),
                  hintText: 'Rechercher par nom'),
              onChanged: (v) => setState(() => _query = v),
            ),
          ),
          if (result?.isCached == true)
            const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: Text('CACHE / OFFLINE',
                    style: TextStyle(color: Colors.orange))),
          Expanded(
            child: _loading && result == null
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    itemCount: all.length + 1,
                    itemBuilder: (context, index) {
                      if (index == all.length) {
                        if (result?.nextCursor == null)
                          return const SizedBox.shrink();
                        return TextButton(
                            onPressed: _loading
                                ? null
                                : () => _load(cursor: result!.nextCursor),
                            child: const Text('Load more'));
                      }
                      final event = all[index];
                      return ListTile(
                        title: Text(event.name),
                        subtitle: Text(
                            '${event.publicationStatus} • ${event.visibility} • ${event.status}'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          if (event.joined) {
                            Navigator.of(context).push(MaterialPageRoute(
                                builder: (_) => EventHubScreen(
                                    eventId: event.id, eventName: event.name)));
                          } else if (event.canManage) {
                            Navigator.of(context).push(MaterialPageRoute(
                                builder: (_) =>
                                    EventManageLandingScreen(event: event)));
                          } else {
                            Navigator.of(context).push(MaterialPageRoute(
                                builder: (_) => EventHubScreen(
                                    eventId: event.id, eventName: event.name)));
                          }
                        },
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
