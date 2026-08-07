import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:get/get.dart';
import 'screens/home_screen.dart';
import 'screens/route_screen.dart';
import 'providers/route_provider.dart';
import 'providers/location_provider.dart';

void main() {
  runApp(const GeuneulApp());
}

class GeuneulApp extends StatelessWidget {
  const GeuneulApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => RouteProvider()),
        ChangeNotifierProvider(create: (_) => LocationProvider()),
      ],
      child: GetMaterialApp(
        title: '그늘로',
        theme: ThemeData(
          primarySwatch: Colors.green,
          useMaterial3: true,
          fontFamily: 'NotoSansKR',
        ),
        home: const HomeScreen(),
        getPages: [
          GetPage(name: '/', page: () => const HomeScreen()),
          GetPage(name: '/route', page: () => const RouteScreen()),
        ],
        debugShowCheckedModeBanner: false,
      ),
    );
  }
}
