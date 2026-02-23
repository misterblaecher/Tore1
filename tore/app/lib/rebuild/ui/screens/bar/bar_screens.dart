import 'package:flutter/material.dart';

import '../../theme/tore_theme.dart';

class BarDashboardScreen extends StatelessWidget { const BarDashboardScreen({super.key}); @override Widget build(BuildContext context)=>_frame('Bar Dashboard',[const ListTile(title:Text('Revenue today'),trailing:Text('€ 2,430',style:TextStyle(fontFamily:'monospace'))),const ListTile(title:Text('Orders live'),trailing:Text('18'))]); }
class OrdersLiveScreen extends StatelessWidget { const OrdersLiveScreen({super.key}); @override Widget build(BuildContext context)=>_frame('Orders Live',[for(final s in ['queued','mixing','served']) ListTile(title:Text('Order #${s.hashCode%1000}'),trailing:Text(s.toUpperCase()))]); }
class FullMenuAdminScreen extends StatelessWidget { const FullMenuAdminScreen({super.key}); @override Widget build(BuildContext context)=>_frame('Full Menu Admin',[const ListTile(title:Text('Product editing shell')),const ListTile(title:Text('Price + tags + stock'))]); }
class ZonesQrAdminScreen extends StatelessWidget { const ZonesQrAdminScreen({super.key}); @override Widget build(BuildContext context)=>_frame('Zones QR Admin',[SwitchListTile(value:true,onChanged:(_){},title:const Text('Zone A enabled')),const ListTile(title:Text('Export zones (stub)'))]); }
class AnalyticsScreen extends StatelessWidget { const AnalyticsScreen({super.key}); @override Widget build(BuildContext context)=>_frame('Analytics',[const Text('Charts placeholder (no extra deps)'),Container(height:120,color:ToreTokens.surfaceAlt),const SizedBox(height:8),Container(height:120,color:ToreTokens.surfaceAlt)]); }

Widget _frame(String title,List<Widget> children)=>Scaffold(appBar:AppBar(title:Text(title)),body:ListView(padding:const EdgeInsets.all(ToreTokens.s12),children:children));
