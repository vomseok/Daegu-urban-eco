import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:get/get.dart';
import '../providers/route_provider.dart';
import '../providers/location_provider.dart';
import '../widgets/shade_chart.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({Key? key}) : super(key: key);

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late TextEditingController _startController;
  late TextEditingController _endController;
  int _selectedHour = 12;

  @override
  void initState() {
    super.initState();
    _startController = TextEditingController();
    _endController = TextEditingController();

    // 그늘 정보 초기 로드
    Future.microtask(() {
      context.read<RouteProvider>().fetchShadeByHour();
    });
  }

  @override
  void dispose() {
    _startController.dispose();
    _endController.dispose();
    super.dispose();
  }

  void _onSearchRoute() async {
    // 현재는 테스트용 좌표 사용
    // 실제로는 Google Places API 통합 필요
    final routeProvider = context.read<RouteProvider>();

    // 대구 임시 좌표
    const double startLat = 35.8721;
    const double startLng = 128.5953;
    const double endLat = 35.9000;
    const double endLng = 128.6200;

    await routeProvider.calculateRoute(
      startLat: startLat,
      startLng: startLng,
      endLat: endLat,
      endLng: endLng,
      hour: _selectedHour,
    );

    if (routeProvider.currentRoute != null && routeProvider.currentRoute!.success) {
      Get.toNamed('/route');
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(routeProvider.error ?? '경로 계산 실패')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🌳 그늘로'),
        elevation: 0,
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ==================== 제목 ====================
              const Text(
                '여름엔 시원하게',
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const Text(
                '그늘길로 경로를 안내해드립니다',
                style: TextStyle(fontSize: 14, color: Colors.grey),
              ),
              const SizedBox(height: 24),

              // ==================== 경로 입력 ====================
              Card(
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      // 출발지
                      TextField(
                        controller: _startController,
                        decoration: InputDecoration(
                          labelText: '출발지',
                          prefixIcon: const Icon(Icons.location_on),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),

                      // 목적지
                      TextField(
                        controller: _endController,
                        decoration: InputDecoration(
                          labelText: '목적지',
                          prefixIcon: const Icon(Icons.location_on_outlined),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // ==================== 시간대 선택 ====================
              Card(
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('출발 시간대',
                          style: TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        children: [
                          for (int hour in [9, 12, 15, 18])
                            FilterChip(
                              label: Text('$hour:00'),
                              selected: _selectedHour == hour,
                              onSelected: (selected) {
                                setState(() => _selectedHour = hour);
                              },
                            ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _selectedHour == 12
                            ? '✨ 정오가 가장 쾌적합니다'
                            : '🌡️ 저녁으로 갈수록 더워집니다',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[700],
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // ==================== 시간대별 그늘 정보 ====================
              Consumer<RouteProvider>(
                builder: (context, routeProvider, _) {
                  if (routeProvider.shadeInfo != null) {
                    return Card(
                      elevation: 2,
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('하루 날씨 예보',
                                style: TextStyle(fontWeight: FontWeight.bold)),
                            const SizedBox(height: 12),
                            ShadeChart(
                              shadeData: routeProvider.shadeInfo!.shadeByHour,
                            ),
                          ],
                        ),
                      ),
                    );
                  }
                  return const SizedBox.shrink();
                },
              ),
              const SizedBox(height: 24),

              // ==================== 검색 버튼 ====================
              Consumer<RouteProvider>(
                builder: (context, routeProvider, _) {
                  return SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: ElevatedButton(
                      onPressed: _onSearchRoute,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green[600],
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: routeProvider.isLoading
                          ? const SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2,
                              ),
                            )
                          : const Text(
                              '쾌적한 경로 찾기',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}
