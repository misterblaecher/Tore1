class CursorPager<T> {
  CursorPager({required this.loader});

  final Future<PagedChunk<T>> Function(String? cursor) loader;
  final List<T> items = <T>[];
  String? _nextCursor;
  bool loading = false;

  bool get hasMore => _nextCursor != null || items.isEmpty;

  Future<void> loadFirst() async {
    items.clear();
    _nextCursor = null;
    await loadMore();
  }

  Future<void> loadMore() async {
    if (loading || (!hasMore && items.isNotEmpty)) return;
    loading = true;
    try {
      final page = await loader(_nextCursor);
      items.addAll(page.items);
      _nextCursor = page.nextCursor;
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
