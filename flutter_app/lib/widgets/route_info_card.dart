import 'package:flutter/material.dart';
import '../models/route_model.dart';

class RouteInfoCard extends StatelessWidget {
  final RouteResponse route;

  const RouteInfoCard({Key? key, required this.route}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final shadeQuality = route.avgShadeScore < 30 ? '매우 좋음' :
                         route.avgShadeScore < 50 ? '좋음' :
                         route.avgShadeScore < 70 ? '보통' : '낮음';
    final shadeColor = route.avgShadeScore < 30 ? Colors.green :
                       route.avgShadeScore < 50 ? Colors.lightGreen :
                       route.avgShadeScore < 70 ? Colors.orange : Colors.red;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ==================== 슬라이더 핸들 ====================
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey[300],
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 16),

          // ==================== 경로 정보 ====================
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              // 거리
              Column(
                children: [
                  const Icon(Icons.route, color: Colors.blue, size: 28),
                  const SizedBox(height: 8),
                  Text(
                    '${(route.distance / 1000).toStringAsFixed(1)} km',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Text('거리', style: TextStyle(fontSize: 12, color: Colors.grey)),
                ],
              ),

              // 소요 시간
              Column(
                children: [
                  const Icon(Icons.schedule, color: Colors.orange, size: 28),
                  const SizedBox(height: 8),
                  Text(
                    '${route.durationMin.toStringAsFixed(0)}분',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Text('소요시간', style: TextStyle(fontSize: 12, color: Colors.grey)),
                ],
              ),

              // 그늘 점수
              Column(
                children: [
                  Icon(Icons.wb_sunny, color: shadeColor, size: 28),
                  const SizedBox(height: 8),
                  Text(
                    '${route.avgShadeScore.toStringAsFixed(0)}점',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: shadeColor,
                    ),
                  ),
                  Text(shadeQuality, style: const TextStyle(fontSize: 12, color: Colors.grey)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),

          // ==================== 버튼 ====================
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.pop(context),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  child: const Text('뒤로'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ElevatedButton(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('네비게이션 시작!')),
                    );
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  child: const Text(
                    '네비게이션 시작',
                    style: TextStyle(color: Colors.white),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
