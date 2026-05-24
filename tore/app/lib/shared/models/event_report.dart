import 'dart:convert';

import 'event_cost.dart';

class EventReport {
  final int eventId;
  final String? generatedAt;
  final EventSales sales;
  final EventCosts costs;
  final EventProfit profit;

  const EventReport({
    required this.eventId,
    required this.generatedAt,
    required this.sales,
    required this.costs,
    required this.profit,
  });

  factory EventReport.fromJson(Map<String, dynamic> json) {
    return EventReport(
      eventId: (json['event_id'] as num?)?.toInt() ?? 0,
      generatedAt: json['generated_at']?.toString(),
      sales: EventSales.fromJson(
        Map<String, dynamic>.from(json['sales'] as Map? ?? const {}),
      ),
      costs: EventCosts.fromJson(
        Map<String, dynamic>.from(json['costs'] as Map? ?? const {}),
      ),
      profit: EventProfit.fromJson(
        Map<String, dynamic>.from(json['profit'] as Map? ?? const {}),
      ),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'event_id': eventId,
      'generated_at': generatedAt,
      'sales': sales.toJson(),
      'costs': costs.toJson(),
      'profit': profit.toJson(),
    };
  }

  String toPrettyJson() {
    return const JsonEncoder.withIndent('  ').convert(toJson());
  }

  String toCsv() {
    final buffer = StringBuffer()..writeln('type,label,qty,revenue_cents');

    for (final item in sales.byItem) {
      buffer.writeln(
        'item,${_csvEscape(item.name)},${item.qty},${item.revenueCents}',
      );
    }
    for (final category in sales.byCategory) {
      buffer.writeln(
        'category,${_csvEscape(category.category)},${category.qty},${category.revenueCents}',
      );
    }
    for (final cost in costs.lines) {
      final label = cost.label.isNotEmpty ? cost.label : cost.category;
      buffer.writeln('cost,${_csvEscape(label)},0,${cost.amountCents}');
    }

    buffer.writeln('summary,gross_revenue,0,${sales.grossRevenueCents}');
    buffer.writeln('summary,total_cost,0,${costs.totalCostCents}');
    buffer.writeln('summary,gross_profit,0,${profit.grossProfitCents}');

    return buffer.toString();
  }

  static String _csvEscape(String value) {
    if (value.contains(',') || value.contains('"') || value.contains('\n')) {
      final escaped = value.replaceAll('"', '""');
      return '"$escaped"';
    }
    return value;
  }
}

class EventSales {
  final int totalOrders;
  final int grossRevenueCents;
  final List<EventSalesItem> byItem;
  final List<EventSalesCategory> byCategory;

  const EventSales({
    required this.totalOrders,
    required this.grossRevenueCents,
    required this.byItem,
    required this.byCategory,
  });

  factory EventSales.fromJson(Map<String, dynamic> json) {
    final rawItems = (json['by_item'] as List? ?? const [])
        .map(
            (e) => EventSalesItem.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    final rawCategories = (json['by_category'] as List? ?? const [])
        .map((e) =>
            EventSalesCategory.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();

    return EventSales(
      totalOrders: (json['total_orders'] as num?)?.toInt() ?? 0,
      grossRevenueCents: (json['gross_revenue_cents'] as num?)?.toInt() ?? 0,
      byItem: rawItems,
      byCategory: rawCategories,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'total_orders': totalOrders,
      'gross_revenue_cents': grossRevenueCents,
      'by_item': byItem.map((e) => e.toJson()).toList(),
      'by_category': byCategory.map((e) => e.toJson()).toList(),
    };
  }
}

class EventSalesItem {
  final int itemId;
  final String name;
  final int qty;
  final int revenueCents;

  const EventSalesItem({
    required this.itemId,
    required this.name,
    required this.qty,
    required this.revenueCents,
  });

  factory EventSalesItem.fromJson(Map<String, dynamic> json) {
    return EventSalesItem(
      itemId: (json['item_id'] as num?)?.toInt() ?? 0,
      name: json['name']?.toString() ?? 'Unknown',
      qty: (json['qty'] as num?)?.toInt() ?? 0,
      revenueCents: (json['revenue_cents'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'item_id': itemId,
      'name': name,
      'qty': qty,
      'revenue_cents': revenueCents,
    };
  }
}

class EventSalesCategory {
  final String category;
  final int qty;
  final int revenueCents;

  const EventSalesCategory({
    required this.category,
    required this.qty,
    required this.revenueCents,
  });

  factory EventSalesCategory.fromJson(Map<String, dynamic> json) {
    return EventSalesCategory(
      category: json['category']?.toString() ?? 'unknown',
      qty: (json['qty'] as num?)?.toInt() ?? 0,
      revenueCents: (json['revenue_cents'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      'qty': qty,
      'revenue_cents': revenueCents,
    };
  }
}

class EventCosts {
  final int totalCostCents;
  final List<EventCost> lines;

  const EventCosts({
    required this.totalCostCents,
    required this.lines,
  });

  factory EventCosts.fromJson(Map<String, dynamic> json) {
    final rawLines = (json['lines'] as List? ?? const [])
        .map((e) => EventCost.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
    return EventCosts(
      totalCostCents: (json['total_cost_cents'] as num?)?.toInt() ?? 0,
      lines: rawLines,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'total_cost_cents': totalCostCents,
      'lines': lines.map((e) => e.toJson()).toList(),
    };
  }
}

class EventProfit {
  final int grossProfitCents;

  const EventProfit({required this.grossProfitCents});

  factory EventProfit.fromJson(Map<String, dynamic> json) {
    return EventProfit(
      grossProfitCents: (json['gross_profit_cents'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'gross_profit_cents': grossProfitCents,
    };
  }
}
