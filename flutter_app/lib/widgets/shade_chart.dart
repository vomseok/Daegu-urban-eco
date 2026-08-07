import 'package:flutter/material.dart';
import '../models/route_model.dart';

class ShadeChart extends StatelessWidget {
  final List<ShadeInfo> shadeData;

  const ShadeChart({Key? key, required this.shadeData}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    if (shadeData.isEmpty) {
      return const Center(child: Text('데이터 없음'));
    }

    final maxShade = shadeData.map((s) => s.shadeScore).reduce((a, b) => a > b ? a : b);
    final minShade = shadeData.map((s) => s.shadeScore).reduce((a, b) => a < b ? a : b);

    return SizedBox(
      height: 150,
      child: Column(
        children: [
          // ==================== 그래프 ====================
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: shadeData.map((shade) {
                final height = (shade.shadeScore / (maxShade > 0 ? maxShade : 100)) * 100;
                final isComfortable = shade.shadeScore < 50;

                return Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Container(
                      width: 30,
                      height: height,
                      decoration: BoxDecoration(
                        color: isComfortable ? Colors.green : Colors.red,
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(4),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${shade.hour}시',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ],
                );
              }).toList(),
            ),
          ),
          const SizedBox(height: 12),

          // ==================== 범례 ====================
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 12,
                height: 12,
                color: Colors.green,
              ),
              const SizedBox(width: 6),
              const Text('쾌적 (<50)', style: TextStyle(fontSize: 12)),
              const SizedBox(width: 16),
              Container(
                width: 12,
                height: 12,
                color: Colors.red,
              ),
              const SizedBox(width: 6),
              const Text('더움 (>50)', style: TextStyle(fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}
