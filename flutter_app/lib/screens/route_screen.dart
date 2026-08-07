import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import '../providers/route_provider.dart';
import '../widgets/route_info_card.dart';

class RouteScreen extends StatefulWidget {
  const RouteScreen({Key? key}) : super(key: key);

  @override
  State<RouteScreen> createState() => _RouteScreenState();
}

class _RouteScreenState extends State<RouteScreen> {
  late GoogleMapController _mapController;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('경로 안내'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Consumer<RouteProvider>(
        builder: (context, routeProvider, _) {
          final route = routeProvider.currentRoute;

          if (route == null || !route.success) {
            return Center(
              child: Text(routeProvider.error ?? '경로 정보 없음'),
            );
          }

          // 경로 폴리라인
          final Set<Polyline> polylines = {
            if (route.path.length > 1)
              Polyline(
                polylineId: const PolylineId('route'),
                points: route.path
                    .map((p) => LatLng(p.lat, p.lng))
                    .toList(),
                color: Colors.green,
                width: 5,
              ),
          };

          // 마커 (출발지, 목적지)
          final Set<Marker> markers = {
            if (route.path.isNotEmpty)
              Marker(
                markerId: const MarkerId('start'),
                position: LatLng(route.path.first.lat, route.path.first.lng),
                infoWindow: const InfoWindow(title: '출발지'),
                icon: BitmapDescriptor.defaultMarkerWithHue(
                    BitmapDescriptor.hueGreen),
              ),
            if (route.path.length > 1)
              Marker(
                markerId: const MarkerId('end'),
                position: LatLng(route.path.last.lat, route.path.last.lng),
                infoWindow: const InfoWindow(title: '목적지'),
                icon:
                    BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueRed),
              ),
          };

          // 지도 초기 위치
          LatLng initialPosition = route.path.isNotEmpty
              ? LatLng(route.path.first.lat, route.path.first.lng)
              : const LatLng(35.8721, 128.5953);

          return Stack(
            children: [
              // ==================== 지도 ====================
              GoogleMap(
                onMapCreated: (controller) => _mapController = controller,
                initialCameraPosition: CameraPosition(
                  target: initialPosition,
                  zoom: 15,
                ),
                polylines: polylines,
                markers: markers,
                myLocationButtonEnabled: false,
              ),

              // ==================== 하단 정보 카드 ====================
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: RouteInfoCard(route: route),
              ),
            ],
          );
        },
      ),
    );
  }
}
