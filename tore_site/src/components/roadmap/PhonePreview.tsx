import { useState } from "react";
import {
  Home,
  ScanLine,
  Radio,
  TrendingUp,
  User,
  Beer,
  Calendar,
  ChevronRight,
  Wifi,
  Battery,
  Signal,
  MapPin,
  Search,
  Bell,
  Wallet,
  UtensilsCrossed,
  Trophy,
  ArrowLeft,
  Plus,
  Minus,
  ShoppingCart,
} from "lucide-react";

type ScreenId = "splash" | "home" | "scanner" | "bars" | "events" | "eventHub" | "menu" | "wallet" | "ticker" | "polymarket" | "profile";

interface NavItem {
  id: ScreenId;
  icon: React.ElementType;
  label: string;
}

const bottomNav: NavItem[] = [
  { id: "home", icon: Home, label: "Découvrir" },
  { id: "events", icon: Calendar, label: "Soirées" },
  { id: "ticker", icon: Radio, label: "Live" },
  { id: "polymarket", icon: TrendingUp, label: "Rooms" },
  { id: "profile", icon: User, label: "Profil" },
];

/* ───── Status Bar ───── */
function StatusBar() {
  return (
    <div className="flex items-center justify-between px-5 pt-3 pb-1 text-[10px] text-white/70">
      <span className="font-semibold">21:37</span>
      <div className="flex items-center gap-1">
        <Signal size={10} />
        <Wifi size={10} />
        <Battery size={10} />
      </div>
    </div>
  );
}

/* ───── Bottom Navigation ───── */
function BottomNav({ active, onNavigate }: { active: ScreenId; onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex items-center justify-around py-2 bg-black/90 border-t border-white/10">
      {bottomNav.map((item) => {
        const isActive = active === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex flex-col items-center gap-0.5 transition-colors ${
              isActive
                ? "text-red-500"
                : "text-white/40 hover:text-white/70"
            }`}
          >
            <item.icon size={18} />
            <span className="text-[9px]">{item.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ───── Screens ───── */
function SplashScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-black" onClick={() => onNavigate("home")}>
      <div className="w-20 h-20 rounded-2xl bg-red-600 flex items-center justify-center shadow-[0_0_40px_rgba(220,38,38,0.4)] mb-4 animate-pulse-glow">
        <span className="text-white font-black text-2xl">T</span>
      </div>
      <h2 className="text-white font-black text-3xl tracking-tight">TORÈ</h2>
      <p className="text-white/40 text-xs mt-2">Tap pour continuer</p>
      <div className="mt-8 w-32 h-0.5 rounded-full bg-yellow-500/60" />
    </div>
  );
}

function HomeScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3">
        <h1 className="text-white font-bold text-lg">TORÈ</h1>
        <div className="flex items-center gap-3">
          <Search size={18} className="text-white/50" />
          <Bell size={18} className="text-white/50" />
        </div>
      </div>

      {/* Discovery CTA */}
      <button
        onClick={() => onNavigate("events")}
        className="mx-4 mb-4 p-4 rounded-2xl bg-gradient-to-r from-red-600/20 to-red-600/5 border border-red-600/30 flex items-center gap-3"
      >
        <div className="w-12 h-12 rounded-xl bg-red-600 flex items-center justify-center">
          <Calendar size={22} className="text-white" />
        </div>
        <div className="text-left">
          <p className="text-white font-semibold text-sm">Soirées autour de toi</p>
          <p className="text-white/40 text-xs">Carré, comités, bars, ce soir…</p>
        </div>
        <ChevronRight size={16} className="text-white/30 ml-auto" />
      </button>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3 px-4 mb-4">
        {[
          { icon: Beer, label: "Bars", color: "bg-amber-500/10 border-amber-500/20", iconColor: "text-amber-400", screen: "bars" as ScreenId },
          { icon: Calendar, label: "Soirées", color: "bg-blue-500/10 border-blue-500/20", iconColor: "text-blue-400", screen: "events" as ScreenId },
          { icon: TrendingUp, label: "Rooms", color: "bg-purple-500/10 border-purple-500/20", iconColor: "text-purple-400", screen: "polymarket" as ScreenId },
          { icon: Wallet, label: "Mémoire", color: "bg-green-500/10 border-green-500/20", iconColor: "text-green-400", screen: "profile" as ScreenId },
        ].map((item) => (
          <button
            key={item.label}
            onClick={() => onNavigate(item.screen)}
            className={`p-3 rounded-xl ${item.color} border flex items-center gap-2.5`}
          >
            <item.icon size={18} className={item.iconColor} />
            <span className="text-white text-xs font-medium">{item.label}</span>
          </button>
        ))}
      </div>

      {/* Nearby */}
      <div className="px-4">
        <h3 className="text-white/60 text-xs font-semibold uppercase mb-2">À proximité</h3>
        {["Le QG", "Bar du Coin", "Nuit Blanche"].map((bar) => (
          <button
            key={bar}
            onClick={() => onNavigate("bars")}
            className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors mb-1"
          >
            <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
              <Beer size={14} className="text-white/50" />
            </div>
            <div className="text-left flex-1">
              <p className="text-white text-xs font-medium">{bar}</p>
              <p className="text-white/30 text-[10px]">
                <MapPin size={8} className="inline mr-0.5" />
                0.{Math.floor(Math.random() * 9) + 1} km
              </p>
            </div>
            <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
          </button>
        ))}
      </div>
    </div>
  );
}

function ScannerScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-black relative">
      {/* Simulated camera bg */}
      <div className="absolute inset-0 bg-gradient-to-b from-neutral-900/80 to-neutral-800/60" />

      {/* Frame */}
      <div className="relative z-10 w-48 h-48 rounded-2xl border-2 border-red-500/80 flex items-center justify-center">
        <div className="absolute inset-0 rounded-2xl shadow-[inset_0_0_30px_rgba(220,38,38,0.15)]" />
        {/* Scan line */}
        <div className="absolute left-2 right-2 h-0.5 bg-red-500/60 animate-[scanLine_2s_ease-in-out_infinite]" />
        <ScanLine size={32} className="text-red-500/30" />
      </div>

      <p className="relative z-10 text-white/50 text-xs mt-6">Pointez vers un QR TORÈ</p>

      {/* Bottom actions */}
      <div className="relative z-10 flex items-center gap-6 mt-8">
        <button className="px-3 py-1.5 rounded-full bg-white/10 text-white/60 text-[10px]">💡 Lampe</button>
        <button
          onClick={() => onNavigate("eventHub")}
          className="px-3 py-1.5 rounded-full bg-white/10 text-white/60 text-[10px]"
        >
          Code manuel
        </button>
      </div>

      <style>{`
        @keyframes scanLine {
          0%, 100% { transform: translateY(-40px); opacity: 0.3; }
          50% { transform: translateY(40px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function BarsScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  const bars = [
    { name: "Le QG", status: "OPEN", statusColor: "bg-green-500" },
    { name: "Nuit Blanche", status: "LIVE EVENT", statusColor: "bg-red-500" },
    { name: "Le Zinc", status: "OPEN", statusColor: "bg-green-500" },
    { name: "L'Appart", status: "CLOSED", statusColor: "bg-white/30" },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("home")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Bars</h1>
      </div>
      <div className="grid grid-cols-2 gap-3 px-4">
        {bars.map((bar) => (
          <button
            key={bar.name}
            onClick={() => bar.status !== "CLOSED" && onNavigate("events")}
            className={`rounded-xl border border-white/10 overflow-hidden ${bar.status === "CLOSED" ? "opacity-40" : "hover:border-white/20"}`}
          >
            <div className="h-16 bg-gradient-to-b from-white/5 to-transparent flex items-end p-2">
              <span className={`text-[8px] font-bold text-white px-1.5 py-0.5 rounded-full ${bar.statusColor}`}>
                {bar.status}
              </span>
            </div>
            <div className="p-2.5">
              <p className="text-white text-xs font-semibold">{bar.name}</p>
              <p className="text-white/30 text-[10px] mt-0.5">Quartier Latin</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function EventsScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("bars")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Nuit Blanche</h1>
      </div>
      {/* Filters */}
      <div className="flex gap-2 px-4 mb-3">
        {["Live", "Today", "Upcoming"].map((f, i) => (
          <span key={f} className={`px-3 py-1 rounded-full text-[10px] font-medium ${i === 0 ? "bg-red-600 text-white" : "bg-white/10 text-white/50"}`}>
            {f}
          </span>
        ))}
      </div>
      {/* Events */}
      {[
        { name: "Soirée 90s", time: "22:00", status: "LIVE", color: "text-red-400" },
        { name: "Karaoké Night", time: "Demain 20:00", status: "UPCOMING", color: "text-blue-400" },
      ].map((e) => (
        <button
          key={e.name}
          onClick={() => onNavigate("eventHub")}
          className="mx-4 mb-2 p-3 rounded-xl bg-white/5 border border-white/10 flex items-center gap-3 hover:bg-white/10 transition"
        >
          <div className="flex-1 text-left">
            <p className="text-white text-xs font-semibold">{e.name}</p>
            <p className="text-white/30 text-[10px] font-mono">{e.time}</p>
          </div>
          <span className={`text-[9px] font-bold ${e.color}`}>{e.status}</span>
        </button>
      ))}
    </div>
  );
}

function EventHubScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("home")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <div>
          <h1 className="text-white font-bold text-base">Soirée 90s</h1>
          <p className="text-red-400 text-[10px] font-semibold">● LIVE</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 px-4">
        {[
          { icon: UtensilsCrossed, label: "Menu", screen: "menu" as ScreenId, color: "border-amber-500/20 bg-amber-500/5" },
          { icon: Wallet, label: "Credits", screen: "wallet" as ScreenId, color: "border-green-500/20 bg-green-500/5" },
          { icon: Radio, label: "Ticker", screen: "ticker" as ScreenId, color: "border-blue-500/20 bg-blue-500/5" },
          { icon: Trophy, label: "Classement", screen: "home" as ScreenId, color: "border-purple-500/20 bg-purple-500/5" },
        ].map((m) => (
          <button
            key={m.label}
            onClick={() => onNavigate(m.screen)}
            className={`p-4 rounded-xl border ${m.color} flex flex-col items-center gap-2 hover:scale-[1.02] transition-transform`}
          >
            <m.icon size={22} className="text-white/70" />
            <span className="text-white text-xs font-medium">{m.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function MenuScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  const [cart, setCart] = useState<Record<string, number>>({});
  const items = [
    { name: "Bière pression", price: "5.00", cat: "Bières" },
    { name: "Cocktail maison", price: "9.50", cat: "Cocktails" },
    { name: "Shot vodka", price: "3.00", cat: "Shots" },
    { name: "Planche mixte", price: "14.00", cat: "Food" },
  ];
  const total = Object.entries(cart).reduce((s, [name, qty]) => {
    const item = items.find((i) => i.name === name);
    return s + (item ? parseFloat(item.price) * qty : 0);
  }, 0);

  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a]">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("eventHub")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Menu</h1>
      </div>
      {/* Filters */}
      <div className="flex gap-2 px-4 mb-3 overflow-x-auto">
        {["Tout", "Bières", "Cocktails", "Shots", "Food"].map((f, i) => (
          <span key={f} className={`px-3 py-1 rounded-full text-[10px] font-medium whitespace-nowrap ${i === 0 ? "bg-red-600 text-white" : "bg-white/10 text-white/50"}`}>
            {f}
          </span>
        ))}
      </div>
      {/* Items */}
      <div className="flex-1 overflow-y-auto px-4 space-y-2">
        {items.map((item) => (
          <div key={item.name} className="flex items-center gap-3 p-2.5 rounded-xl bg-white/5">
            <div className="flex-1">
              <p className="text-white text-xs font-medium">{item.name}</p>
              <p className="text-white/60 text-[10px] font-mono">{item.price} €</p>
            </div>
            <div className="flex items-center gap-2">
              {(cart[item.name] || 0) > 0 && (
                <>
                  <button onClick={() => setCart(c => ({ ...c, [item.name]: Math.max(0, (c[item.name] || 0) - 1) }))} className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center">
                    <Minus size={10} className="text-white/60" />
                  </button>
                  <span className="text-white text-xs font-mono w-4 text-center">{cart[item.name]}</span>
                </>
              )}
              <button onClick={() => setCart(c => ({ ...c, [item.name]: (c[item.name] || 0) + 1 }))} className="w-5 h-5 rounded-full bg-red-600 flex items-center justify-center">
                <Plus size={10} className="text-white" />
              </button>
            </div>
          </div>
        ))}
      </div>
      {/* Cart bar */}
      {total > 0 && (
        <div className="mx-4 mb-3 p-3 rounded-xl bg-yellow-500 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShoppingCart size={14} className="text-black" />
            <span className="text-black text-xs font-bold">{Object.values(cart).reduce((a, b) => a + b, 0)} items</span>
          </div>
          <span className="text-black text-xs font-bold font-mono">{total.toFixed(2)} €</span>
        </div>
      )}
    </div>
  );
}

function WalletScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("home")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Credits</h1>
      </div>
      <div className="mx-4 p-6 rounded-2xl bg-gradient-to-br from-white/10 to-white/5 border border-white/10 text-center mb-4">
        <p className="text-white/40 text-[10px] uppercase tracking-wider">Credits</p>
        <p className="text-white text-4xl font-black font-mono mt-1">245</p>
      </div>
      <div className="px-4">
        <h3 className="text-white/40 text-[10px] uppercase tracking-wider mb-2">Historique</h3>
        {[
          { label: "Bière pression ×2", amount: "-100", time: "21:15" },
          { label: "Ajout staff", amount: "+300", time: "20:30" },
          { label: "Reward soirée", amount: "+50", time: "20:45" },
        ].map((tx) => (
          <div key={tx.label + tx.time} className="flex items-center justify-between py-2.5 border-b border-white/5">
            <div>
              <p className="text-white text-xs">{tx.label}</p>
              <p className="text-white/30 text-[10px] font-mono">{tx.time}</p>
            </div>
            <span className={`text-xs font-mono font-bold ${tx.amount.startsWith("+") ? "text-green-400" : "text-white/60"}`}>
              {tx.amount}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TickerScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("home")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Ticker Live</h1>
        <span className="ml-auto w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
      </div>
      <div className="px-4 space-y-2">
        {[
          { text: "🍺 Alex a commandé 3 bières", time: "il y a 2min", color: "border-amber-500/20" },
          { text: "🎲 Nouvelle room : \"Le DJ passe du Daft Punk avant minuit\"", time: "il y a 5min", color: "border-purple-500/20" },
          { text: "📢 Happy hour prolongée jusqu'à 23h !", time: "il y a 8min", color: "border-red-500/20" },
          { text: "🏆 Marie est #1 au classement", time: "il y a 12min", color: "border-yellow-500/20" },
        ].map((e, i) => (
          <div key={i} className={`p-3 rounded-xl bg-white/5 border ${e.color}`}>
            <p className="text-white text-xs">{e.text}</p>
            <p className="text-white/30 text-[9px] mt-1">{e.time}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniChart({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 80;
  const h = 28;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`).join(" ");
  return (
    <svg width={w} height={h} className="shrink-0">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PolymarketScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  const [picks, setPicks] = useState<Record<string, "yes" | "no" | null>>({});
  const rooms = [
    { q: "Le DJ passe du Daft Punk avant minuit ?", yes: 72, chart: [30, 45, 55, 60, 58, 65, 72], hot: true },
    { q: "Plus de 200 personnes ce soir ?", yes: 45, chart: [50, 48, 42, 40, 38, 43, 45], hot: false },
    { q: "Happy hour prolongée après 23h ?", yes: 88, chart: [60, 65, 70, 78, 80, 85, 88], hot: true },
    { q: "Le bar à shots ouvre avant 22h ?", yes: 31, chart: [20, 25, 35, 30, 28, 33, 31], hot: false },
    { q: "Karaoké avant la fermeture ?", yes: 56, chart: [40, 50, 55, 52, 58, 54, 56], hot: false },
  ];

  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="flex items-center gap-3 px-4 py-3">
        <button onClick={() => onNavigate("home")}>
          <ArrowLeft size={18} className="text-white/60" />
        </button>
        <h1 className="text-white font-bold text-base">Rooms</h1>
        <span className="ml-auto px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 text-[9px] font-bold">BETA</span>
      </div>

      {/* Stats bar */}
      <div className="flex gap-3 px-4 mb-3">
        {[
          { label: "Rooms", value: "5" },
          { label: "Participants", value: "47" },
          { label: "Mes points", value: "320" },
        ].map((s) => (
          <div key={s.label} className="flex-1 p-2 rounded-lg bg-white/5 text-center">
            <p className="text-white text-xs font-bold font-mono">{s.value}</p>
            <p className="text-white/30 text-[8px]">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Markets */}
      <div className="px-4 space-y-2 pb-2">
        {rooms.map((m, i) => {
          const userPick = picks[m.q];
          const yesColor = m.yes >= 60 ? "#22c55e" : m.yes >= 40 ? "#eab308" : "#ef4444";
          return (
            <div key={i} className="p-3 rounded-xl bg-white/5 border border-white/10">
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-white text-[11px] font-medium leading-tight flex-1">
                  {m.hot && <span className="text-red-400 mr-1">🔥</span>}
                  {m.q}
                </p>
                <MiniChart data={m.chart} color={yesColor} />
              </div>
              {/* Probability bar */}
              <div className="w-full h-1.5 rounded-full bg-white/10 mb-2 overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${m.yes}%`, backgroundColor: yesColor }} />
              </div>
              {/* Bet buttons */}
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPicks((b) => ({ ...b, [m.q]: b[m.q] === "yes" ? null : "yes" }))}
                  className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold transition-all ${
                    userPick === "yes"
                      ? "bg-green-500 text-black"
                      : "bg-green-500/10 text-green-400 border border-green-500/20"
                  }`}
                >
                  Oui {m.yes}%
                </button>
                <button
                  onClick={() => setPicks((b) => ({ ...b, [m.q]: b[m.q] === "no" ? null : "no" }))}
                  className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold transition-all ${
                    userPick === "no"
                      ? "bg-red-500 text-white"
                      : "bg-red-500/10 text-red-400 border border-red-500/20"
                  }`}
                >
                  Non {100 - m.yes}%
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProfileScreen({ onNavigate }: { onNavigate: (s: ScreenId) => void }) {
  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0a] overflow-y-auto">
      <div className="px-4 py-3">
        <h1 className="text-white font-bold text-base">Profil</h1>
      </div>
      <div className="flex flex-col items-center py-4">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-red-600 to-red-800 flex items-center justify-center mb-2">
          <User size={28} className="text-white" />
        </div>
        <p className="text-white font-semibold text-sm">Lucas M.</p>
        <p className="text-white/40 text-[10px]">@lucas_tore</p>
      </div>
      <div className="px-4 space-y-1">
        {["Mes events", "Historique", "Paramètres", "Confidentialité", "Aide"].map((item) => (
          <button key={item} className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-white/5 transition">
            <span className="text-white text-xs">{item}</span>
            <ChevronRight size={14} className="text-white/20" />
          </button>
        ))}
      </div>
    </div>
  );
}

/* ───── Main Component ───── */
const screens: Record<ScreenId, string> = {
  splash: "Splash",
  home: "Home",
  scanner: "QR contextuel",
  bars: "Bars",
  events: "Events",
  eventHub: "Hub soirée",
  menu: "Menu",
  wallet: "Credits",
  ticker: "Ticker",
  polymarket: "Rooms",
  profile: "Profil",
};

export default function PhonePreview() {
  const [currentScreen, setCurrentScreen] = useState<ScreenId>("splash");
  const showNav = currentScreen !== "splash" && currentScreen !== "scanner";

  const renderScreen = () => {
    const props = { onNavigate: setCurrentScreen };
    switch (currentScreen) {
      case "splash": return <SplashScreen {...props} />;
      case "home": return <HomeScreen {...props} />;
      case "scanner": return <ScannerScreen {...props} />;
      case "bars": return <BarsScreen {...props} />;
      case "events": return <EventsScreen {...props} />;
      case "eventHub": return <EventHubScreen {...props} />;
      case "menu": return <MenuScreen {...props} />;
      case "wallet": return <WalletScreen {...props} />;
      case "ticker": return <TickerScreen {...props} />;
      case "polymarket": return <PolymarketScreen {...props} />;
      case "profile": return <ProfileScreen {...props} />;
    }
  };

  return (
    <section className="py-16 md:py-24 bg-surface/50">
      <div className="container">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-6">
            <Calendar className="text-primary" size={18} />
            <span className="text-sm font-medium">Preview Interactive</span>
          </div>
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Explore l'app <span className="text-primary neon-text">TORÈ</span>
          </h2>
          <p className="text-muted-foreground max-w-xl mx-auto">
            Navigue dans le prototype interactif. Clique sur les éléments pour explorer chaque écran.
          </p>
        </div>

        <div className="flex flex-col lg:flex-row items-center justify-center gap-10">
          {/* Phone */}
          <div className="relative">
            {/* Phone frame */}
            <div className="w-[280px] h-[580px] rounded-[40px] bg-gradient-to-b from-neutral-800 to-neutral-900 p-[3px] shadow-[0_0_60px_rgba(0,0,0,0.5)]">
              <div className="w-full h-full rounded-[37px] bg-black overflow-hidden flex flex-col relative">
                {/* Notch */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-28 h-6 bg-black rounded-b-2xl z-20" />
                <StatusBar />
                {renderScreen()}
                {showNav && <BottomNav active={currentScreen} onNavigate={setCurrentScreen} />}
                {/* Home indicator */}
                <div className="flex justify-center py-1.5 bg-black">
                  <div className="w-24 h-1 rounded-full bg-white/20" />
                </div>
              </div>
            </div>
          </div>

          {/* Screen selector */}
          <div className="flex flex-col gap-2 max-w-[200px]">
            <p className="text-xs text-muted-foreground mb-1 font-semibold uppercase">Écrans</p>
            {(Object.entries(screens) as [ScreenId, string][]).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setCurrentScreen(id)}
                className={`px-3 py-2 rounded-lg text-xs text-left transition-all ${
                  currentScreen === id
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-primary/30"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
