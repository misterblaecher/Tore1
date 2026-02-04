import 'package:tore/core/network/api_client.dart';
import 'package:tore/core/network/api_endpoints.dart';
import 'market_models.dart';

class MarketRepository {
  final ApiClient api;
  MarketRepository(this.api);

  Future<List<MarketDrink>> fetchMenu({required int eventId}) async {
    final r = await api.dio.get(ApiEndpoints.eventMenu(eventId));
    final list = (r.data as List).cast<dynamic>();
    return list
        .map((e) => MarketDrink.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
  }

  /// POST /orders
  Future<void> createOrder({
    required int eventId,
    required String userId,
    required List<OrderItemIn> items,
    String payMode = 'tickets',
    bool isGift = false,
    String? giftToUserId,
  }) async {
    final payload = <String, dynamic>{
      'event_id': eventId,
      'user_id': userId,
      'pay_mode': payMode,
      'items': items.map((i) => i.toJson()).toList(),
      'is_gift': isGift,
      'gift_to_user_id': giftToUserId,
    };

    await api.dio.post(ApiEndpoints.orders, data: payload);
  }
}
