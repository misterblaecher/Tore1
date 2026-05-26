import 'package:flutter/material.dart';

import '../../../models/qr_resolve.dart';
import '../../../models/rebuild_types.dart';
import '../../../routing/app_routes.dart';
import '../../theme/tore_theme.dart';
import '../../widgets/primitives.dart';

class BootSplashScreen extends StatelessWidget {
  const BootSplashScreen(
      {super.key,
      required this.network,
      required this.environmentLabel,
      required this.environmentColor,
      this.onLongPressDiagnostics});
  final ConnectivityState network;
  final String environmentLabel;
  final Color environmentColor;
  final VoidCallback? onLongPressDiagnostics;
  @override
  Widget build(BuildContext context) => GestureDetector(
        onLongPress: onLongPressDiagnostics,
        child: Scaffold(
          body: SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(ToreTokens.s24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Image.asset('assets/branding/logo_full_fire.png',
                        height: 150, fit: BoxFit.contain),
                    const SizedBox(height: ToreTokens.s24),
                    Text('Préparation de votre soirée',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: ToreTokens.s12),
                    const LinearProgressIndicator(
                      minHeight: 5,
                      color: ToreTokens.yellowCta,
                      backgroundColor: ToreTokens.surfaceAlt,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
}

class ConsentCharterScreen extends StatelessWidget {
  const ConsentCharterScreen({super.key, required this.onAccept});
  final VoidCallback onAccept;
  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Padding(
            padding: ToreTokens.pagePadding,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Spacer(),
                Image.asset('assets/branding/logo_full_fire.png',
                    height: 120, fit: BoxFit.contain),
                const SizedBox(height: ToreTokens.s24),
                Text('L’OS des soirées étudiantes',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: ToreTokens.s8),
                const Text(
                  'Scanner, commander, voter et suivre l’ambiance live depuis un seul hub.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: ToreTokens.s24),
                Card(
                  child: Padding(
                    padding: EdgeInsets.all(ToreTokens.s12),
                    child: Column(children: [
                      ListTile(
                        leading: Icon(Icons.qr_code_scanner,
                            color: ToreTokens.yellowCta),
                        title: Text('Scanner universel'),
                        subtitle: Text('Event, menu, WiFi, staff et tickets.'),
                      ),
                      Divider(color: ToreTokens.border, height: 1),
                      ListTile(
                        leading:
                            Icon(Icons.show_chart, color: ToreTokens.yellowCta),
                        title: Text('Bets & classement live'),
                        subtitle: Text('Une soirée lisible, fun et traçable.'),
                      ),
                    ]),
                  ),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: onAccept,
                  child: const Text('Entrer dans TORÈ'),
                ),
              ],
            ),
          ),
        ),
      );
}

class HomeHubScreen extends StatelessWidget {
  const HomeHubScreen({super.key, required this.network, required this.cards});
  final ConnectivityState network;
  final List<Widget> cards;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Home Hub',
        connectivity: network,
        scopeBadges: const ['USER', 'LIVE'],
        body: cards.isEmpty
            ? const EmptyStateView(
                message: 'Aucun module actif pour le moment.')
            : ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: cards.length,
                separatorBuilder: (_, __) =>
                    const SizedBox(height: ToreTokens.s8),
                itemBuilder: (_, i) => cards[i]),
      );
}

class QrScannerScreen extends StatelessWidget {
  const QrScannerScreen(
      {super.key,
      required this.onResolve,
      this.network = ConnectivityState.online});
  final Future<void> Function(String payload) onResolve;
  final ConnectivityState network;

  @override
  Widget build(BuildContext context) {
    final ctrl = TextEditingController();

    Future<void> handleResolve() async {
      final payload = ctrl.text.trim();
      if (payload.isEmpty) {
        ToreFeedback.warning(context, 'Saisissez un code pour continuer.');
        return;
      }
      ToreFeedback.success(context, 'QR reçu, résolution en cours...');
      await onResolve(payload);
      if (!context.mounted) return;
      final normalized = normalizeUiCode(payload.split(':').first);
      final copy = resolveUiCopy(normalized);
      if (uiCopyMapping.containsKey(normalized)) {
        ToreFeedback.error(context, '${copy.title} — ${copy.message}');
      } else {
        ToreFeedback.success(context, 'QR accepté. Action lancée.');
      }
    }

    return ScreenScaffold(
      title: 'QR Scanner',
      connectivity: network,
      scopeBadges: const ['USER', 'SCAN'],
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        AnimatedScale(
          scale: 1,
          duration: ToreMotion.micro(context),
          child: Container(
            height: 220,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: ToreTokens.ruby, width: 2),
              color: ToreTokens.surfaceAlt,
            ),
            child: const Center(
                child: Icon(Icons.qr_code_scanner,
                    size: 64, color: ToreTokens.ruby)),
          ),
        ),
        const SizedBox(height: ToreTokens.s8),
        const Text(
            'Cadrez le QR dans la zone rubis. Le scan se lance automatiquement.'),
        const SizedBox(height: ToreTokens.s12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(ToreTokens.s12),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text('Saisie manuelle',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: ToreTokens.s8),
                  Semantics(
                    textField: true,
                    label: 'QR manual input',
                    child: TextField(
                        controller: ctrl,
                        decoration: const InputDecoration(
                            labelText: 'Code ou payload QR')),
                  ),
                  const SizedBox(height: ToreTokens.s12),
                  Row(children: [
                    Expanded(
                        child: OutlinedButton(
                            onPressed: () => ToreFeedback.success(context,
                                'Torche prête pour faciliter le scan.'),
                            child: const Text('Torche'))),
                    const SizedBox(width: ToreTokens.s8),
                    Expanded(
                        child: OutlinedButton(
                            onPressed: () => _showScannerHelp(context),
                            child: const Text('Aide'))),
                  ]),
                  const SizedBox(height: ToreTokens.s8),
                  FilledButton(
                      onPressed: handleResolve,
                      child: const Text('Résoudre le code')),
                ]),
          ),
        ),
      ]),
    );
  }
}

class BarsScreen extends StatelessWidget {
  const BarsScreen({super.key, required this.network, required this.children});
  final ConnectivityState network;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Bars',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: children.length,
          itemBuilder: (_, i) => children[i]));
}

class BarEventsScreen extends StatelessWidget {
  const BarEventsScreen(
      {super.key,
      required this.children,
      this.network = ConnectivityState.online});
  final List<Widget> children;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Events',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          Wrap(spacing: ToreTokens.s8, children: const [
            Chip(label: Text('Live')),
            Chip(label: Text('Today')),
            Chip(label: Text('Upcoming'))
          ]),
          const SizedBox(height: ToreTokens.s8),
          ...children
        ]),
      );
}

class JoinEventScreen extends StatelessWidget {
  const JoinEventScreen(
      {super.key,
      required this.writeAllowed,
      required this.onJoin,
      this.network = ConnectivityState.online});
  final bool writeAllowed;
  final VoidCallback onJoin;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Join Event',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          const TextField(
              decoration: InputDecoration(labelText: 'Optional code')),
          const SizedBox(height: ToreTokens.s8),
          if (!writeAllowed)
            const BlockedStateView(
                title: 'Entrée temporairement bloquée',
                message:
                    'L’action est indisponible: module gelé, lecture seule ou réseau hors ligne.'),
          const SizedBox(height: ToreTokens.s8),
          Semantics(
            button: true,
            label: 'JOIN',
            child: FilledButton(
              style: FilledButton.styleFrom(
                  backgroundColor: ToreTokens.yellowCta,
                  foregroundColor: Colors.black),
              onPressed: writeAllowed ? onJoin : null,
              child: const Text('Join'),
            ),
          ),
        ]),
      );
}

class EventHubScreen extends StatelessWidget {
  const EventHubScreen({
    super.key,
    required this.network,
    required this.modules,
    this.eventState = EventState.live,
    this.writeAllowedReason = 'Actions disponibles',
  });
  final ConnectivityState network;
  final List<Widget> modules;
  final EventState eventState;
  final String writeAllowedReason;

  @override
  Widget build(BuildContext context) {
    final labels = {
      EventState.live: 'LIVE',
      EventState.paused: 'PAUSED',
      EventState.readOnly: 'MENU_ONLY',
      EventState.ended: 'CLOSED',
      EventState.draft: 'DRAFT',
    };
    final stateLabel = labels[eventState] ?? 'LIVE';
    final ctaEnabled =
        network != ConnectivityState.offline && eventState.isLive;
    return ScreenScaffold(
      title: 'Event Hub',
      connectivity: network,
      scopeBadges: const ['USER', 'HUB'],
      body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Card(
          child: ListTile(
            title: Text('État événement: $stateLabel'),
            subtitle: Text(writeAllowedReason),
            trailing: ToreBadge(
                label: stateLabel,
                color: eventState == EventState.paused
                    ? Colors.orange
                    : ToreTokens.ruby),
          ),
        ),
        const SizedBox(height: ToreTokens.s8),
        if (modules.isEmpty)
          const EmptyStateView(
              message:
                  'Aucun module actif. Les modules OFF restent invisibles.')
        else
          ...modules,
        const SizedBox(height: ToreTokens.s8),
        FilledButton(
            onPressed: ctaEnabled
                ? () => Navigator.pushNamed(context, AppRoutes.menu)
                : null,
            child: const Text('Ouvrir le menu')),
      ]),
    );
  }
}

class WalletScreen extends StatelessWidget {
  const WalletScreen(
      {super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Wallet',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('€ 129.20', style: ToreTypography.monoNumber(context, size: 36)),
          const SizedBox(height: ToreTokens.s12),
          if (rows.isEmpty)
            const EmptyStateView(message: 'Aucun mouvement pour le moment.'),
          ...rows,
        ]),
      );
}

class TickerScreen extends StatelessWidget {
  const TickerScreen(
      {super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Ticker',
        connectivity: network,
        scopeBadges: const ['USER'],
        body: Column(children: [
          Row(children: [
            OutlinedButton(
                onPressed: () => _showTickerFilters(context),
                child: const Text('Filtres')),
            const SizedBox(width: ToreTokens.s8),
            OutlinedButton(
                onPressed: () =>
                    ToreFeedback.success(context, 'Ticker mis en pause.'),
                child: const Text('Pause'))
          ]),
          const SizedBox(height: ToreTokens.s8),
          ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: rows.length,
              itemBuilder: (_, i) => rows[i]),
        ]),
      );
}

void _showScannerHelp(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: ToreTokens.surface,
    builder: (context) => Padding(
      padding: ToreTokens.pagePadding,
      child: Column(mainAxisSize: MainAxisSize.min, children: const [
        ListTile(
          leading: Icon(Icons.qr_code_scanner),
          title: Text('Scanner un QR'),
          subtitle: Text('Cadrez le QR événement, menu, WiFi ou invitation.'),
        ),
        ListTile(
          leading: Icon(Icons.flashlight_on),
          title: Text('Lumière faible'),
          subtitle: Text('Activez la torche si le scan est difficile.'),
        ),
      ]),
    ),
  );
}

void _showTickerFilters(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: ToreTokens.surface,
    builder: (context) => Padding(
      padding: ToreTokens.pagePadding,
      child: Column(mainAxisSize: MainAxisSize.min, children: const [
        SwitchListTile(value: true, onChanged: null, title: Text('Annonces')),
        SwitchListTile(value: true, onChanged: null, title: Text('Commandes')),
        SwitchListTile(value: true, onChanged: null, title: Text('Bets')),
      ]),
    ),
  );
}

class PolymarketGlobalScreen extends StatelessWidget {
  const PolymarketGlobalScreen(
      {super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Marchés globaux',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: rows.length,
          itemBuilder: (_, i) => rows[i]));
}

class PolymarketEventScreen extends StatelessWidget {
  const PolymarketEventScreen(
      {super.key, required this.rows, this.network = ConnectivityState.online});
  final List<Widget> rows;
  final ConnectivityState network;
  @override
  Widget build(BuildContext context) => ScreenScaffold(
      title: 'Marchés de la soirée',
      connectivity: network,
      scopeBadges: const ['USER'],
      body: ListView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: rows.length,
          itemBuilder: (_, i) => rows[i]));
}

class ProfileSettingsScreen extends StatefulWidget {
  const ProfileSettingsScreen(
      {super.key,
      this.network = ConnectivityState.online,
      this.onOpenDiagnostics,
      this.onOpenHelp});
  final ConnectivityState network;
  final VoidCallback? onOpenDiagnostics;
  final VoidCallback? onOpenHelp;

  @override
  State<ProfileSettingsScreen> createState() => _ProfileSettingsScreenState();
}

class _ProfileSettingsScreenState extends State<ProfileSettingsScreen> {
  bool reduceMotion = false;
  bool hideBalance = true;
  bool notifications = true;
  late final TextEditingController nameCtrl;
  late final TextEditingController handleCtrl;
  late final TextEditingController phoneCtrl;
  late final TextEditingController oripeauxCtrl;
  late final TextEditingController capCtrl;
  late final TextEditingController functionCtrl;
  late final TextEditingController gradeCtrl;
  late final TextEditingController affiliationCtrl;

  @override
  void initState() {
    super.initState();
    nameCtrl = TextEditingController(text: 'Alex Martin');
    handleCtrl = TextEditingController(text: '@alex.tore');
    phoneCtrl = TextEditingController(text: '+33 6 12 34 56 78');
    oripeauxCtrl =
        TextEditingController(text: 'Tablier rubis · épitoge ULiège');
    capCtrl = TextEditingController(text: 'Penne facultaire');
    functionCtrl = TextEditingController(text: 'Délégué events');
    gradeCtrl = TextEditingController(text: 'Ancien bleu · parrain');
    affiliationCtrl = TextEditingController(text: 'Comité Saint-Torè');
  }

  @override
  void dispose() {
    nameCtrl.dispose();
    handleCtrl.dispose();
    phoneCtrl.dispose();
    oripeauxCtrl.dispose();
    capCtrl.dispose();
    functionCtrl.dispose();
    gradeCtrl.dispose();
    affiliationCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ScreenScaffold(
        title: 'Profil',
        connectivity: widget.network,
        body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(ToreTokens.s16),
              child: Row(children: [
                Container(
                  width: 68,
                  height: 68,
                  decoration: BoxDecoration(
                    color: ToreTokens.ruby,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: ToreTokens.yellowCta),
                  ),
                  child: const Icon(Icons.add_a_photo, color: Colors.white),
                ),
                const SizedBox(width: ToreTokens.s12),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(nameCtrl.text,
                            style: Theme.of(context).textTheme.titleLarge),
                        Text(handleCtrl.text),
                        const SizedBox(height: ToreTokens.s4),
                        const Text('Photo, rôles et appartenance folklore'),
                      ]),
                ),
                IconButton(
                  tooltip: 'Aide',
                  onPressed: widget.onOpenHelp,
                  icon: const Icon(Icons.help_outline),
                ),
              ]),
            ),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: nameCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Nom affiché', prefixIcon: Icon(Icons.badge)),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: handleCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Pseudo', prefixIcon: Icon(Icons.alternate_email)),
            onChanged: (_) => setState(() {}),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: phoneCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            keyboardType: TextInputType.phone,
            decoration: const InputDecoration(
                labelText: 'Téléphone', prefixIcon: Icon(Icons.phone)),
          ),
          const SizedBox(height: ToreTokens.s16),
          Text('Identité folklorique',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: ToreTokens.s8),
          TextField(
            controller: oripeauxCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Oripeaux estudiantins',
                prefixIcon: Icon(Icons.auto_awesome)),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: capCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Penne / calotte / casquette',
                prefixIcon: Icon(Icons.school)),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: functionCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Fonction dans le comité',
                prefixIcon: Icon(Icons.groups)),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: gradeCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Grades ou rôles',
                prefixIcon: Icon(Icons.military_tech)),
          ),
          const SizedBox(height: ToreTokens.s12),
          TextField(
            controller: affiliationCtrl,
            style: const TextStyle(color: Colors.white),
            cursorColor: ToreTokens.yellowCta,
            decoration: const InputDecoration(
                labelText: 'Comité, ordre ou rivageoise',
                prefixIcon: Icon(Icons.account_balance)),
          ),
          const SizedBox(height: ToreTokens.s16),
          Card(
            child: Column(children: [
              SwitchListTile(
                  value: notifications,
                  onChanged: (v) => setState(() => notifications = v),
                  title: const Text('Notifications soirée'),
                  subtitle: const Text('Entrées, commandes et temps forts')),
              SwitchListTile(
                  value: hideBalance,
                  onChanged: (v) => setState(() => hideBalance = v),
                  title: const Text('Masquer le solde'),
                  subtitle: const Text('Protection sur écran verrouillé')),
              const Divider(color: ToreTokens.border, height: 1),
              SwitchListTile(
                  value: true,
                  onChanged: (_) {},
                  title: const Text('Profil public forum'),
                  subtitle:
                      const Text('Afficher pseudo, fonction et affiliation')),
              SwitchListTile(
                  value: false,
                  onChanged: (_) {},
                  title: const Text('Afficher téléphone'),
                  subtitle: const Text('Désactivé par défaut')),
            ]),
          ),
          const SizedBox(height: ToreTokens.s12),
          ValueListenableBuilder<bool>(
            valueListenable: TorePreferences.highContrast,
            builder: (context, value, _) => SwitchListTile(
              value: value,
              onChanged: (next) => TorePreferences.highContrast.value = next,
              title: const Text('Contraste renforcé'),
            ),
          ),
          SwitchListTile(
              value: reduceMotion,
              onChanged: (v) => setState(() => reduceMotion = v),
              title: const Text('Réduire les animations')),
          const SizedBox(height: ToreTokens.s12),
          FilledButton.icon(
              onPressed: () =>
                  ToreFeedback.success(context, 'Profil mis à jour'),
              icon: const Icon(Icons.check),
              label: const Text('Enregistrer')),
        ]),
      );
}
