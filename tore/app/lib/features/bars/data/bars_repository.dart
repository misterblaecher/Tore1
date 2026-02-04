import 'package:dio/dio.dart';
import '../../../shared/models/bar.dart';

class BarsRepository {
  final Dio _dio;
  BarsRepository(this._dio);

  Future<List<Bar>> fetchBars() async {
    final res = await _dio.get('/bars');
    final data = (res.data as List).cast<dynamic>();
    return data
        .map((e) => Bar.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }
}
