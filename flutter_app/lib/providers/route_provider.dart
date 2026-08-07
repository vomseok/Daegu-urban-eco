import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';
import '../models/route_model.dart';

class RouteProvider extends ChangeNotifier {
  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: 'http://localhost:8000/api',
      connectTimeout: const Duration(seconds: 5),
      receiveTimeout: const Duration(seconds: 10),
    ),
  );

  RouteResponse? _currentRoute;
  bool _isLoading = false;
  String? _error;
  DayShadeResponse? _shadeInfo;

  RouteResponse? get currentRoute => _currentRoute;
  bool get isLoading => _isLoading;
  String? get error => _error;
  DayShadeResponse? get shadeInfo => _shadeInfo;

  /// 경로 계산 요청
  Future<void> calculateRoute({
    required double startLat,
    required double startLng,
    required double endLat,
    required double endLng,
    required int hour,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/route',
        data: {
          'start': {'lat': startLat, 'lng': startLng},
          'end': {'lat': endLat, 'lng': endLng},
          'hour': hour,
        },
      );

      if (response.data != null) {
        _currentRoute = RouteResponse.fromJson(response.data!);
      }
    } catch (e) {
      _error = '경로 계산 실패: $e';
      debugPrint(_error);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// 시간대별 그늘 정보 조회
  Future<void> fetchShadeByHour() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/shade-by-hour',
      );

      if (response.data != null) {
        _shadeInfo = DayShadeResponse.fromJson(response.data!);
      }
    } catch (e) {
      debugPrint('그늘 정보 조회 실패: $e');
    }
    notifyListeners();
  }

  void clearRoute() {
    _currentRoute = null;
    _error = null;
    notifyListeners();
  }
}
