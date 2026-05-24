class CursorPager<T> {
  CursorPager({required this.loader});

  final Future<PagedChunk<T>> Function(String? cursor) loader;
  final List<T> items = <T>[];
  String? _nextCursor;
  String? _lastCursorSeen;
  bool _stopped = false;
  bool loading = false;

  bool get hasMore => !_stopped && (_nextCursor != null || items.isEmpty);

  Future<void> loadFirst() async {
    items.clear();
    _nextCursor = null;
    _lastCursorSeen = null;
    _stopped = false;
    await loadMore();
  }

  Future<void> loadMore() async {
    if (loading || (!hasMore && items.isNotEmpty)) return;
    loading = true;
    try {
      final currentCursor = _nextCursor;
      final page = await loader(currentCursor);
      items.addAll(page.items);
      final next = page.nextCursor?.trim();
      if (next == null ||
          next.isEmpty ||
          next == currentCursor ||
          next == _lastCursorSeen) {
        _nextCursor = null;
        _stopped = true;
      } else {
        _lastCursorSeen = currentCursor;
        _nextCursor = next;
      }
    } finally {
      loading = false;
    }
  }
}

class PagedChunk<T> {
  const PagedChunk({required this.items, this.nextCursor});

  final List<T> items;
  final String? nextCursor;
}
