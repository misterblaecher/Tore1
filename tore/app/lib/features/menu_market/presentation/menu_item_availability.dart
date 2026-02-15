enum MenuItemStockState { inStock, low, out, unknown }

MenuItemStockState menuItemStockState(Map<String, dynamic> item) {
  final available = item['available'];
  if (available is bool && available == false) {
    return MenuItemStockState.out;
  }

  final stockStatus = item['stockStatus'] ?? item['stock_status'];
  if (stockStatus == null) {
    return MenuItemStockState.unknown;
  }

  final normalized = stockStatus.toString().trim().toUpperCase();
  switch (normalized) {
    case 'OUT':
      return MenuItemStockState.out;
    case 'LOW':
      return MenuItemStockState.low;
    case 'IN':
      return MenuItemStockState.inStock;
    default:
      return MenuItemStockState.unknown;
  }
}

bool isMenuItemOut(Map<String, dynamic> item) {
  return menuItemStockState(item) == MenuItemStockState.out;
}
