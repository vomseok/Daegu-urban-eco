class Location {
  final double lat;
  final double lng;

  Location({required this.lat, required this.lng});

  factory Location.fromJson(Map<String, dynamic> json) {
    return Location(
      lat: (json['lat'] as num).toDouble(),
      lng: (json['lng'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
    'lat': lat,
    'lng': lng,
  };
}

class RouteResponse {
  final bool success;
  final double distance;
  final double avgShadeScore;
  final double durationMin;
  final List<Location> path;
  final String message;

  RouteResponse({
    required this.success,
    required this.distance,
    required this.avgShadeScore,
    required this.durationMin,
    required this.path,
    required this.message,
  });

  factory RouteResponse.fromJson(Map<String, dynamic> json) {
    return RouteResponse(
      success: json['success'] as bool,
      distance: (json['distance'] as num).toDouble(),
      avgShadeScore: (json['avg_shade_score'] as num).toDouble(),
      durationMin: (json['duration_min'] as num).toDouble(),
      path: (json['path'] as List)
          .map((p) => Location.fromJson(p as Map<String, dynamic>))
          .toList(),
      message: json['message'] as String,
    );
  }
}

class ShadeInfo {
  final int hour;
  final double shadeScore;

  ShadeInfo({required this.hour, required this.shadeScore});

  factory ShadeInfo.fromJson(Map<String, dynamic> json) {
    return ShadeInfo(
      hour: json['hour'] as int,
      shadeScore: (json['shade_score'] as num).toDouble(),
    );
  }
}

class DayShadeResponse {
  final List<ShadeInfo> shadeByHour;
  final int bestTime;
  final int worstTime;

  DayShadeResponse({
    required this.shadeByHour,
    required this.bestTime,
    required this.worstTime,
  });

  factory DayShadeResponse.fromJson(Map<String, dynamic> json) {
    return DayShadeResponse(
      shadeByHour: (json['shade_by_hour'] as List)
          .map((s) => ShadeInfo.fromJson(s as Map<String, dynamic>))
          .toList(),
      bestTime: json['best_time'] as int,
      worstTime: json['worst_time'] as int,
    );
  }
}
