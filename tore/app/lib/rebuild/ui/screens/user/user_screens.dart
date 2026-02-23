import 'package:flutter/material.dart';

import '../../../models/rebuild_types.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BootSplashScreen extends StatelessWidget {
  const BootSplashScreen({super.key, required this.network});
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => _Frame(title: 'Boot', network: network, child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [SkeletonBlock(), SkeletonBlock(), Text('TORÈ v3 rebuild boot…'), Text('Offline mode supported')])) ;
}

class ConsentCharterScreen extends StatelessWidget {
  const ConsentCharterScreen({super.key, required this.onAccept});
  final VoidCallback onAccept;
  @override
  Widget build(BuildContext context) => _Frame(title: 'Consent Charter', child: Column(children: [const Text('Night charter consent required.'), const SizedBox(height: 12), FilledButton(onPressed: onAccept, child: const Text('Accept & continue'))]));
}

class HomeHubScreen extends StatelessWidget {
  const HomeHubScreen({super.key, required this.network, required this.cards});
  final ConnectivityState network;
  final List<Widget> cards;
  @override
  Widget build(BuildContext context) => _Frame(title: 'Home Hub', network: network, child: Column(children: cards));
}

class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen({super.key, required this.onResolve});
  final Future<void> Function(String payload) onResolve;

  @override
  Widget build(BuildContext context) {
    final ctrl = TextEditingController();
    return _Frame(
      title: 'QR Scanner',
      child: Column(children: [
        Container(height: 160, color: ToreTokens.surfaceAlt, child: const Center(child: Icon(Icons.qr_code_scanner, size: 56))),
        const SizedBox(height: 12),
        TextField(controller: ctrl, decoration: const InputDecoration(labelText: 'QR payload')),
        const SizedBox(height: 12),
        FilledButton(onPressed: () => onResolve(ctrl.text), child: const Text('Resolve QR')),
      ]),
    );
  }
}

class BarsScreen extends StatelessWidget { const BarsScreen({super.key, required this.network, required this.children}); final ConnectivityState network; final List<Widget> children; @override Widget build(BuildContext context)=>_Frame(title:'Bars',network:network,child:Column(children:children)); }
class BarEventsScreen extends StatelessWidget { const BarEventsScreen({super.key, required this.children}); final List<Widget> children; @override Widget build(BuildContext context)=>_Frame(title:'Events',child:Column(children:[Wrap(spacing:8,children:const [Chip(label: Text('Live')),Chip(label: Text('Today')),Chip(label: Text('Upcoming'))]),const SizedBox(height:8),...children])); }
class JoinEventScreen extends StatelessWidget { const JoinEventScreen({super.key, required this.writeAllowed, required this.onJoin}); final bool writeAllowed; final VoidCallback onJoin; @override Widget build(BuildContext context)=>_Frame(title:'Join Event',child:Column(children:[const TextField(decoration: InputDecoration(labelText:'Optional code')),const SizedBox(height:8),FilledButton(style: FilledButton.styleFrom(backgroundColor:ToreTokens.yellowCta,foregroundColor:Colors.black),onPressed: writeAllowed?onJoin:null,child:const Text('Join'))])); }
class EventHubScreen extends StatelessWidget { const EventHubScreen({super.key, required this.network, required this.modules}); final ConnectivityState network; final List<Widget> modules; @override Widget build(BuildContext context)=>_Frame(title:'Event Hub',network:network,child:Column(children:modules)); }
class MenuScreen extends StatelessWidget { const MenuScreen({super.key, required this.network, required this.items}); final ConnectivityState network; final List<Widget> items; @override Widget build(BuildContext context)=>_Frame(title:'Menu',network:network,child:Column(children:[...items,const SizedBox(height:8),Container(padding:const EdgeInsets.all(12),color:ToreTokens.surfaceAlt,child:const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,children:[Text('Cart total'),Text('42.00',style:TextStyle(fontFamily:'monospace'))]))])); }
class WalletScreen extends StatelessWidget { const WalletScreen({super.key, required this.rows}); final List<Widget> rows; @override Widget build(BuildContext context)=>_Frame(title:'Wallet',child:Column(children:[const Text('€ 129.20',style:TextStyle(fontFamily:'monospace',fontSize:32,fontWeight:FontWeight.bold)),const SizedBox(height:8),...rows])); }
class TickerScreen extends StatelessWidget { const TickerScreen({super.key, required this.rows}); final List<Widget> rows; @override Widget build(BuildContext context)=>_Frame(title:'Ticker',child:Column(children:[Row(children:[OutlinedButton(onPressed:(){},child:const Text('Filters')),const SizedBox(width:8),OutlinedButton(onPressed:(){},child:const Text('Pause'))]),const SizedBox(height:8),...rows])); }
class PolymarketGlobalScreen extends StatelessWidget { const PolymarketGlobalScreen({super.key, required this.rows}); final List<Widget> rows; @override Widget build(BuildContext context)=>_Frame(title:'Polymarket Global',child:Column(children:rows)); }
class PolymarketEventScreen extends StatelessWidget { const PolymarketEventScreen({super.key, required this.rows}); final List<Widget> rows; @override Widget build(BuildContext context)=>_Frame(title:'Polymarket Event',child:Column(children:rows)); }
class ProfileSettingsScreen extends StatelessWidget { const ProfileSettingsScreen({super.key}); @override Widget build(BuildContext context)=>_Frame(title:'Profile Settings',child:Column(children:[const ListTile(title:Text('Privacy'),subtitle:Text('public / friends / private')),SwitchListTile(value:true,onChanged:(_){},title:const Text('Night theme')),SwitchListTile(value:false,onChanged:(_){},title:const Text('Accessibility high contrast'))])); }

class _Frame extends StatelessWidget {
  const _Frame({required this.title, required this.child, this.network});
  final String title;
  final Widget child;
  final ConnectivityState? network;
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(title)),
        body: ListView(padding: const EdgeInsets.all(ToreTokens.s12), children: [if (network != null) NetworkBanner(state: network!), child]),
      );
}
