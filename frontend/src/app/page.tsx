"use client";

import {
  Activity,
  ArrowUpRight,
  Bell,
  ChevronRight,
  Gauge,
  Info,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  DELAYED_BANNER_TEXT,
  type AttentionSignal,
  type AttentionWatchlistResponse,
  type CatchMeUpResponse,
  type ChangeStoryResponse,
  fetchAttentionWatchlist,
  fetchCatchMeUp,
  fetchChangeStory,
  isDelayedApiError,
  registerNotificationToken,
} from "../services/api";
import { getBrowserFcmToken } from "../services/firebase-messaging";

const DEMO_USER_ID = "00000000-0000-4000-8000-000000000001";

type Stock = {
  symbol: string;
  name: string;
  mci: number;
  price: string;
  change: string;
  volume: string;
  sector: string;
  technicals: string;
  summary: string;
  reason: string;
  signal: {
    price: number;
    volume: number;
    sector: number;
    technicals: number;
  };
  mciBreakdown: {
    price: number;
    volume: number;
    relative: number;
    event: number;
  };
  what: string;
  why: string;
  now: string;
  changed: { label: string; value: string }[];
  unchanged: { label: string; value: string }[];
};

const STOCKS: Stock[] = [
  {
    symbol: "RELIANCE",
    name: "Reliance Industries",
    mci: 92,
    price: "₹2,914.40",
    change: "+4.8%",
    volume: "1.2M",
    sector: "Energy",
    technicals: "Bullish",
    summary: "Refining and telecom continue to widen operating leverage.",
    reason: "Outperformed the sector by 3.4% on 2.8× normal volume.",
    signal: { price: 90, volume: 76, sector: 68, technicals: 94 },
    mciBreakdown: { price: 25, volume: 24, relative: 20, event: 23 },
    what: "A sharp rebound in upstream and refining margins pushed earnings momentum higher.",
    why: "Crude spreads improved and Jio ARPU resilience kept the telecom business stable across the cycle.",
    now: "Price is holding above the 20-day VWAP and continues to build momentum with higher participation.",
    changed: [
      { label: "Price action", value: "Breakout above 20-day VWAP" },
      { label: "Volume", value: "2.8× normal trading volume" },
      { label: "Sector flow", value: "Energy outperforming benchmark" },
    ],
    unchanged: [
      { label: "Valuation", value: "Still premium to sector median" },
      { label: "Options flow", value: "Neutral risk skew" },
      { label: "News sentiment", value: "Mixed but constructive" },
    ],
  },
  {
    symbol: "TCS",
    name: "Tata Consultancy Services",
    mci: 71,
    price: "₹3,842.10",
    change: "+1.9%",
    volume: "680K",
    sector: "IT",
    technicals: "Positive",
    summary: "Large deal commentary remains constructive even as the market digests macro softness.",
    reason: "Climbed on improving deal pipeline while the sector remained broadly calm.",
    signal: { price: 73, volume: 61, sector: 77, technicals: 70 },
    mciBreakdown: { price: 22, volume: 18, relative: 17, event: 14 },
    what: "Deal wins and resilient services demand are being priced back into the stock.",
    why: "Analysts are seeing better conversion from the large-deal pipeline versus earlier quarters.",
    now: "Momentum remains positive, though a stronger dollar backdrop would help the next leg higher.",
    changed: [
      { label: "Deal pipeline", value: "Large deals accelerating" },
      { label: "FX sensitivity", value: "Recent USD strength helps margin" },
      { label: "Trend", value: "Higher lows sustained" },
    ],
    unchanged: [
      { label: "Valuation", value: "Highest in peer group" },
      { label: "Macro risk", value: "Client budgets still cautious" },
      { label: "AI-related spend", value: "Not yet broad-based" },
    ],
  },
  {
    symbol: "HDFCBANK",
    name: "HDFC Bank",
    mci: 58,
    price: "₹1,728.75",
    change: "+1.2%",
    volume: "2.4M",
    sector: "Banking",
    technicals: "Stable",
    summary: "Healthy deposit mix and strong credit quality keep the setup steady.",
    reason: "Bid held firm as funding and liquidity conditions stayed supportive.",
    signal: { price: 60, volume: 54, sector: 67, technicals: 52 },
    mciBreakdown: { price: 18, volume: 16, relative: 13, event: 11 },
    what: "The stock is absorbing broader market volatility without losing structure.",
    why: "Funding costs remain manageable and loan growth continues to hold up despite rate pressure.",
    now: "This is a watchlist name rather than a breakout setup; it needs a stronger trigger to lead.",
    changed: [
      { label: "Funding mix", value: "Deposit growth stable" },
      { label: "Credit quality", value: "Maintaining strength" },
      { label: "Relative trend", value: "Flat trend but steady" },
    ],
    unchanged: [
      { label: "Momentum", value: "Not yet accelerating" },
      { label: "Volatility", value: "Moderate" },
      { label: "Risk appetite", value: "Selective" },
    ],
  },
  {
    symbol: "INFY",
    name: "Infosys",
    mci: 44,
    price: "₹1,482.90",
    change: "+0.8%",
    volume: "960K",
    sector: "IT",
    technicals: "Neutral",
    summary: "Large-cap IT is still in a wait-and-watch phase amid slow discretionary spending.",
    reason: "Only a modest move versus the sector without a strong volume impulse.",
    signal: { price: 39, volume: 45, sector: 50, technicals: 48 },
    mciBreakdown: { price: 12, volume: 11, relative: 10, event: 11 },
    what: "The name has not broken through a meaningful trend change yet.",
    why: "Macro softness and delayed project spend continue to cap the upside.",
    now: "Muted price action suggests investors should stay patient rather than chase the move.",
    changed: [
      { label: "Guidance", value: "Still cautious" },
      { label: "Large deals", value: "Selective conversion" },
      { label: "Trend", value: "Range-bound" },
    ],
    unchanged: [
      { label: "Risk profile", value: "Lower beta" },
      { label: "Cash generation", value: "Strong" },
      { label: "Sentiment", value: "Neutral" },
    ],
  },
  {
    symbol: "SBIN",
    name: "State Bank of India",
    mci: 63,
    price: "₹866.55",
    change: "+2.6%",
    volume: "5.1M",
    sector: "Banking",
    technicals: "Improving",
    summary: "Public sector lenders continue to lead on earnings quality and asset quality trends.",
    reason: "Outpaced peers while maintaining steady credit quality and volume.",
    signal: { price: 68, volume: 72, sector: 60, technicals: 57 },
    mciBreakdown: { price: 20, volume: 18, relative: 13, event: 12 },
    what: "The stock is responding to a tighter fiscal backdrop and stronger bank earnings momentum.",
    why: "Cost-to-income improvement and consistent credit discipline keep sentiment constructive.",
    now: "There is a healthy trend, but it is not yet in the highest-risk attention tier.",
    changed: [
      { label: "Loan growth", value: "Improving across segments" },
      { label: "Credit quality", value: "Stable with margin support" },
      { label: "Market leadership", value: "PSU banks outperforming" },
    ],
    unchanged: [
      { label: "Valuation", value: "Above some private banks" },
      { label: "Risk appetite", value: "Moderate" },
      { label: "Volatility", value: "Elevated but controlled" },
    ],
  },
  {
    symbol: "LTIM",
    name: "LTIMindtree",
    mci: 33,
    price: "₹5,412.60",
    change: "-0.4%",
    volume: "310K",
    sector: "IT",
    technicals: "Weak",
    summary: "No meaningful change in trend; the setup remains subdued versus peers.",
    reason: "Fell against the sector with thin participation and weak trend support.",
    signal: { price: 28, volume: 34, sector: 42, technicals: 38 },
    mciBreakdown: { price: 9, volume: 9, relative: 8, event: 7 },
    what: "The stock is still in a weak pulse pattern and has not improved materially.",
    why: "Project delays and softer discretionary spend continue to cap the near-term narrative.",
    now: "This remains a low-priority name unless volume and relative strength improve meaningfully.",
    changed: [
      { label: "Momentum", value: "Cooling off" },
      { label: "Buy interest", value: "Light" },
      { label: "Trend", value: "Below short-term average" },
    ],
    unchanged: [
      { label: "Fundamentals", value: "Not compelling yet" },
      { label: "Delivery volume", value: "Thin" },
      { label: "Sentiment", value: "Muted" },
    ],
  },
];

const freshness = { live: false, label: "DEMO MODE · Simulated market data" };

function formatPrice(price: number) {
  return `₹${price.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function attentionSignalToStock(signal: AttentionSignal): Stock {
  const priceChange = `${signal.price_delta_pct >= 0 ? "+" : ""}${signal.price_delta_pct.toFixed(2)}%`;
  return {
    symbol: signal.symbol,
    name: signal.company_name,
    mci: Math.round(signal.mci_score),
    price: formatPrice(signal.price),
    change: priceChange,
    volume: "Live",
    sector: "Market",
    technicals: signal.priority,
    summary: signal.summary,
    reason: signal.summary,
    signal: { price: 0, volume: 0, sector: 0, technicals: 0 },
    mciBreakdown: {
      price: Math.round(signal.breakdown.price ?? 0),
      volume: Math.round(signal.breakdown.volume ?? 0),
      relative: Math.round(signal.breakdown.relative ?? 0),
      event: Math.round(signal.breakdown.event ?? 0),
    },
    what: signal.summary,
    why: `The signal is ranked ${signal.priority} with an MCI score of ${Math.round(signal.mci_score)}.`,
    now: "Watch the next market update for confirmation.",
    changed: [
      { label: "Price movement", value: `${priceChange} since last snapshot` },
      { label: "Signal priority", value: signal.priority },
      { label: "MCI score", value: `${Math.round(signal.mci_score)} / 100` },
    ],
    unchanged: [],
  };
}

function getPriority(mci: number) {
  if (mci > 75) return { label: "HIGH ATTENTION", tone: "critical" };
  if (mci >= 50) return { label: "WORTH A LOOK", tone: "watch" };
  return { label: "QUIET", tone: "low" };
}

function getPriceTone(changeText: string) {
  if (changeText.startsWith("-")) return "text-[#FF4D5A]";
  if (changeText.startsWith("+")) return "text-[#00D09C]";
  return "text-[#9aa7b0]";
}

export default function Home() {
  const [selected, setSelected] = useState<Stock>(STOCKS[0]);
  const [watchlistData, setWatchlistData] = useState<AttentionWatchlistResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStory, setSelectedStory] = useState<ChangeStoryResponse | null>(null);
  const [catchUpData, setCatchUpData] = useState<CatchMeUpResponse | null>(null);
  const [catchUpLoading, setCatchUpLoading] = useState(false);
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [alertToast, setAlertToast] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [storyOpen, setStoryOpen] = useState(false);
  const [mciExpanded, setMciExpanded] = useState(true);

  useEffect(() => {
    setAlertsEnabled(window.localStorage.getItem("groww-signal-alerts-enabled") === "true");
  }, []);

  useEffect(() => {
    let active = true;

    const loadWatchlist = async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const response = await fetchAttentionWatchlist(DEMO_USER_ID);
        if (!active) return;
        setWatchlistData(response);
        setError(null);
        if (response.stocks.length > 0) {
          setSelected(attentionSignalToStock(response.stocks[0]));
        }
      } catch (requestError) {
        if (!active) return;
        setError(isDelayedApiError(requestError) ? DELAYED_BANNER_TEXT : "Unable to refresh signals");
      } finally {
        if (active && !silent) setLoading(false);
      }
    };

    void loadWatchlist();
    const intervalId = window.setInterval(() => void loadWatchlist(true), 15000);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const stocks = watchlistData?.stocks?.length
    ? watchlistData.stocks.map(attentionSignalToStock)
    : STOCKS;

  const countSummary = {
    high: stocks.filter((stock) => stock.mci > 75).length,
    watch: stocks.filter((stock) => stock.mci >= 50 && stock.mci <= 75).length,
    quiet: stocks.filter((stock) => stock.mci < 50).length,
  };

  const breakdown = [
    ["Price Movement", selected.mciBreakdown.price],
    ["Volume Anomaly", selected.mciBreakdown.volume],
    ["Relative Performance", selected.mciBreakdown.relative],
    ["Event Signal", selected.mciBreakdown.event],
  ] as const;

  const totalBreakdownScore = breakdown.reduce((sum, [, value]) => sum + value, 0);

  const handleStockSelect = async (stock: Stock) => {
    setSelected(stock);
    setSelectedStory(null);
    setStoryOpen(true);
    try {
      const story = await fetchChangeStory(stock.symbol);
      setSelectedStory(story);
      setError(null);
    } catch (requestError) {
      setError(isDelayedApiError(requestError) ? DELAYED_BANNER_TEXT : "Unable to load change story");
    }
  };

  const handleCatchMeUp = async () => {
    setDrawerOpen(true);
    setCatchUpLoading(true);
    try {
      const summary = await fetchCatchMeUp(DEMO_USER_ID);
      setCatchUpData(summary);
      setError(null);
    } catch (requestError) {
      setError(isDelayedApiError(requestError) ? DELAYED_BANNER_TEXT : "Unable to load market brief");
    } finally {
      setCatchUpLoading(false);
    }
  };

  const handleEnableAlerts = async () => {
    if (!("Notification" in window)) {
      setAlertToast("Browser notifications are not supported here.");
      return;
    }

    const permission = Notification.permission === "default"
      ? await Notification.requestPermission()
      : Notification.permission;

    if (permission === "granted") {
      try {
        const token = await getBrowserFcmToken();
        if (!token) {
          setAlertToast("Add Firebase web configuration to register push alerts.");
        } else {
          const registration = await registerNotificationToken(token);
          if (!registration.registered) throw new Error("Token registration failed");
          window.localStorage.setItem("groww-signal-alerts-enabled", "true");
          setAlertsEnabled(true);
          setAlertToast("Alerts enabled for critical watchlist updates.");
        }
      } catch {
        setAlertToast("Unable to register push alerts right now.");
      }
    } else {
      setAlertToast("Notification permission is required to enable alerts.");
    }
    window.setTimeout(() => setAlertToast(null), 3500);
  };

  return (
    <div className="min-h-screen bg-[#0B0F0E] text-white">
      <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
        <header className="rounded-[24px] border border-[#26312E] bg-[#111817] px-4 py-4 sm:px-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#00D09C] text-[#0B0F0E] shadow-[0_0_18px_rgba(0,208,156,0.22)]">
                <Activity className="h-4 w-4" />
              </div>
              <div>
                <p className="text-lg font-semibold tracking-[-0.03em] text-white">Groww Signal</p>
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b949e]">ATTENTION ENGINE</p>
              </div>
            </div>

            <div className="flex items-center gap-3 self-start lg:self-auto">
              <button
                type="button"
                onClick={() => void handleEnableAlerts()}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[9px] font-semibold uppercase tracking-[0.12em] transition ${alertsEnabled ? "border-[#00D09C]/40 bg-[#00D09C]/10 text-[#00D09C]" : "border-[#26312E] bg-[#151C1A] text-[#F5F7F6] hover:border-[#00B386]"}`}
              >
                <Bell className="h-3.5 w-3.5" />
                {alertsEnabled ? "Alerts Enabled" : "Enable Push Alerts"}
              </button>
              <div className="flex items-center gap-2 rounded-full border border-[#243039] bg-[#0f1519]/90 px-2.5 py-1.5 text-[9px] font-medium tracking-[0.12em] text-[#dfe7eb] uppercase">
                <span className="inline-block h-2 w-2 rounded-full bg-[#39d98a] shadow-[0_0_8px_rgba(57,217,138,0.9)]" />
                <span>{watchlistData ? "● LIVE · FASTAPI MARKET DATA" : `● ${freshness.label.toUpperCase()}`}</span>
              </div>
              <button className="flex h-9 w-9 items-center justify-center rounded-full border border-[#2a3138] bg-[#171d23] text-[#cfdbed] hover:border-[#3a424b]">
                <Search className="h-4 w-4" />
              </button>
              <button className="flex h-9 w-9 items-center justify-center rounded-full border border-[#2a3138] bg-[#171d23] text-[#cfdbed] hover:border-[#3a424b]">
                <Bell className="h-4 w-4" />
              </button>
            </div>
          </div>

          {alertToast && (
            <div className="mt-3 rounded-xl border border-[#00D09C]/30 bg-[#151C1A] px-3 py-2 text-center text-xs text-[#00D09C]" role="status">
              {alertToast}
            </div>
          )}

          {error && (
            <div className="mt-3 flex items-center gap-2 rounded-xl border border-[#F5B83D]/30 bg-[#151C1A] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#F5B83D]">
              <span>{error}</span>
              <span className="font-normal normal-case tracking-normal text-[#9AA6A2]">Showing the last available signals.</span>
            </div>
          )}

          <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-[#2a3138] bg-[#0e1418] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full bg-[#123f33] text-[#7af0c8]">
                <Sparkles className="h-3.5 w-3.5" />
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-[#7af0c8]">WELCOME BACK</p>
                <p className="mt-1 text-[15px] leading-6 text-[#edf3f5]">
                  <span className="font-semibold text-white">Since you last checked 13h 21m ago</span>
                  <span className="text-[#b8c2c7]"> — </span>
                  <span className="font-medium text-[#f3f6f7]">{countSummary.high} High Attention</span>
                  <span className="text-[#b8c2c7]"> | </span>
                  <span className="font-medium text-[#f3f6f7]">{countSummary.watch} Worth a Look</span>
                  <span className="text-[#b8c2c7]"> | </span>
                  <span className="font-medium text-[#f3f6f7]">{countSummary.quiet} Quiet</span>
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => void handleCatchMeUp()}
              className="inline-flex items-center justify-center gap-2 self-start rounded-full bg-[#f3f6f8] px-4 py-2 text-sm font-semibold text-[#0e1418] transition hover:bg-white"
            >
              Catch Me Up
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main className="mt-6 grid gap-6 xl:grid-cols-[1.85fr_0.95fr]">
          <section className="rounded-[26px] border border-[#26312E] bg-[#111817] p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3 pb-2">
              <div>
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#7e8b95]">ATTENTION RADAR</p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">Stocks in focus</h2>
                <p className="mt-1 text-xs text-[#8e9aa3]">Ranked by what deserves your attention.</p>
              </div>

              <div className="flex items-center gap-2 rounded-full border border-[#293640] bg-[#0f171d] px-2.5 py-1.5 text-[10px] uppercase tracking-[0.12em] text-[#9bb2c4]">
                <Gauge className="h-3.5 w-3.5 text-[#7af0c8]" />
                Sorted by MCI score
              </div>
            </div>

            {loading ? (
              <div className="mt-5 flex min-h-48 items-center justify-center rounded-2xl border border-[#26312E] bg-[#0B0F0E]">
                <div className="h-7 w-7 animate-spin rounded-full border-2 border-[#26312E] border-t-[#00D09C]" aria-label="Loading signals" />
              </div>
            ) : (
            <div className="mt-5 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {stocks.map((stock) => {
                const priority = getPriority(stock.mci);
                return (
                  <button
                    key={stock.symbol}
                    type="button"
                    onClick={() => void handleStockSelect(stock)}
                    className="group flex w-full flex-col rounded-[22px] border border-[#26312E] bg-[#111817] p-3.5 text-left transition duration-200 hover:-translate-y-0.5 hover:border-[#00B386]"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-[10px] uppercase tracking-[0.18em] text-[#d3dce3]">{stock.symbol}</p>
                        <p className="mt-1.5 text-[15px] font-semibold text-white">{stock.name}</p>
                      </div>
                      <span className="rounded-full border border-white/10 bg-[#0f171d] px-2 py-1 text-[8px] font-semibold uppercase tracking-[0.14em] text-[#f4f9fb]">
                        {priority.label}
                      </span>
                    </div>

                    <div className="mt-3 flex items-end justify-between">
                      <div className="text-[22px] font-semibold tracking-[-0.05em] text-white">{stock.price}</div>
                      <div className={`text-[11px] font-medium ${getPriceTone(stock.change)}`}>{stock.change}</div>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-[9px] uppercase tracking-[0.14em] text-[#9aa7b0]">
                      <span>MCI</span>
                      <span className="text-[#edf5f6]">{stock.mci}</span>
                    </div>

                    <p className="mt-3 min-h-5 truncate text-[12px] leading-5 text-[#dfe8ee]" title={stock.reason}>{stock.reason}</p>

                    <div className="mt-3 flex w-full items-center justify-between rounded-xl border border-[#2f3a43] bg-[#10171c] px-3 py-2 text-[10px] font-medium uppercase tracking-[0.14em] text-[#edf5f6] transition hover:border-[#536674] hover:bg-[#121c22]">
                      <span>See Why It Matters</span>
                      <ChevronRight className="h-4 w-4" />
                    </div>
                  </button>
                );
              })}
            </div>
            )}
          </section>

          <aside className="space-y-4">
            <div className="rounded-[24px] border border-[#26312E] bg-[#111817] p-4">
              <p className="text-[11px] uppercase tracking-[0.22em] text-[#7e8b95]">MARKET PULSE</p>
              <div className="mt-5 space-y-3">
                <div className="flex items-center justify-between rounded-2xl border border-[#23333d] bg-[#0d1418] px-3 py-2.5">
                  <span className="text-sm text-[#d7e1e5]">{countSummary.high} High Attention</span>
                  <span className="text-lg font-semibold text-[#F5B83D]">{countSummary.high}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-[#31352d] bg-[#101712] px-3 py-2.5">
                  <span className="text-sm text-[#d7e1e5]">{countSummary.watch} Worth a Look</span>
                  <span className="text-lg font-semibold text-[#F5B83D]">{countSummary.watch}</span>
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-[#23332d] bg-[#0d1514] px-3 py-2.5">
                  <span className="text-sm text-[#d7e1e5]">{countSummary.quiet} Quiet</span>
                  <span className="text-lg font-semibold text-[#7ae7b9]">{countSummary.quiet}</span>
                </div>
              </div>

              <div className="mt-5 rounded-2xl border border-[#2a3138] bg-[#0d1418] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b949e]">Most unusual right now</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-white">{selected.symbol}</p>
                    <p className="text-xs text-[#b9c4ca]">MCI {selected.mci}</p>
                  </div>
                  <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${getPriceTone(selected.change)}`}>{selected.change}</span>
                </div>
              </div>
            </div>
          </aside>
        </main>

        <div className="mt-6 rounded-[24px] border border-[#2a3138] bg-[#10171c] p-4">
          <p className="text-[11px] uppercase tracking-[0.22em] text-[#7e8b95]">SINCE YOU LAST CHECKED</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {stocks.slice(0, 3).map((stock) => (
              <div key={stock.symbol} className="rounded-2xl border border-[#2a3138] bg-[#0d1418] p-3">
                <p className="text-[10px] uppercase tracking-[0.18em] text-[#8b949e]">{stock.symbol}</p>
                <div className="mt-2 flex items-center justify-between gap-3 text-sm text-[#edf3f6]">
                  <span>{stock.price}</span>
                  <span className={getPriceTone(stock.change)}>{stock.change}</span>
                </div>
                <p className="mt-2 text-[10px] uppercase tracking-[0.14em] text-[#7e8b95]">13h 21m ago</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]">
          <div className="absolute inset-y-0 right-0 w-full max-w-md border-l border-[#2a3138] bg-[#12181d] p-5 shadow-2xl shadow-black/50 transition-transform duration-300">
            <div className="flex items-center justify-between border-b border-[#272f38] pb-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-[#8b949e]">Catch Me Up</p>
                <h3 className="mt-2 text-2xl font-semibold text-white">YOUR MARKET BRIEF</h3>
              </div>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-[#2a3138] bg-[#171d23] text-[#dfe8ee]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-[#2a3138] bg-[#0d1418] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#8b949e]">While you were away...</p>
                {catchUpLoading ? (
                  <div className="mt-2 flex items-center gap-2 text-sm text-[#9AA6A2]">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#26312E] border-t-[#00D09C]" />
                    Loading your market brief...
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-[#edf3f6]">
                    {catchUpData?.summary ?? `${stocks.slice(0, 3).length} things changed meaningfully.`}
                  </p>
                )}
              </div>

              {(catchUpData?.critical_changes ?? stocks.slice(0, 3).map((stock) => ({
                symbol: stock.symbol,
                headline: undefined,
                mci: stock.mci,
                change: stock.change,
                reason: stock.reason,
              }))).map((change) => (
                <div key={change.symbol} className="rounded-2xl border border-[#2a3138] bg-[#0d1418] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-[#a9b2b9]">{change.symbol}</p>
                      <p className="mt-1 text-base font-semibold text-white">{change.mci ? `MCI ${change.mci}` : "Critical change"}</p>
                    </div>
                    <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${getPriceTone(change.change ?? "")}`}>{change.change}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[#dfe8ed]">{change.headline ?? change.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {storyOpen && (
        <div className="fixed inset-0 z-30 flex justify-end bg-black/50 backdrop-blur-[2px]">
          <div className="h-full w-full max-w-xl border-l border-[#26312E] bg-[#111817] p-4 shadow-2xl shadow-black/60 lg:p-5">
            <div className="flex items-start justify-between gap-4 border-b border-[#2a3138] pb-3">
              <div>
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b949e]">CHANGE STORY</p>
                <h3 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-white">{selected.symbol}</h3>
                <p className="mt-1 text-sm text-[#b7c1c6]">{selected.name}</p>
              </div>

              <button
                type="button"
                onClick={() => setStoryOpen(false)}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-[#2a3138] bg-[#171d23] text-[#dfe8ee]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3 overflow-y-auto pb-2">
              <div className="rounded-[20px] border border-[#2a3138] bg-[#0d1418] p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[9px] uppercase tracking-[0.2em] text-[#8b949e]">MEANINGFUL CHANGE INDEX</p>
                    <p className="mt-2 text-4xl font-semibold leading-none text-white">{selected.mci} <span className="text-lg text-[#8b949e]">/ 100</span></p>
                  </div>
                  <span className="rounded-full border border-[#2a3138] bg-[#141d22] px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.18em] text-[#f7fbfd]">
                    {getPriority(selected.mci).label}
                  </span>
                </div>
                <p className="mt-3 text-[10px] uppercase tracking-[0.14em] text-[#8b949e]">Measures significance, not direction.</p>
                <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/10">
                  <div
                    className={`h-full rounded-full ${selected.mci >= 50 ? "bg-[#F5B83D]" : "bg-[#00D09C]"}`}
                    style={{ width: `${selected.mci}%` }}
                  />
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.24em] text-[#8b949e]">WHAT CHANGED</p>
                <div className="mt-3 space-y-2 text-sm text-[#edf3f6]">
                  <div className="flex items-center justify-between"><span>Price</span><span className={getPriceTone(selected.change)}>{selected.change}</span></div>
                  <div className="flex items-center justify-between"><span>Volume</span><span>{selected.volume}</span></div>
                  <div className="flex items-center justify-between"><span>52W High</span><span>Tested</span></div>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b949e]">MARKET CONTEXT</p>
                <div className="mt-3 space-y-2 text-sm text-[#edf3f6]">
                  <div className="flex justify-between"><span>Nifty IT</span><span className="text-[#3ad598]">↑ 0.90%</span></div>
                  <div className="flex justify-between"><span>Nifty</span><span className="text-[#3ad598]">↑ 0.15%</span></div>
                  <div className="flex justify-between"><span>Rupee</span><span className="text-[#a5afb7]">↔ Flat</span></div>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b949e]">SINCE YOUR LAST CHECK</p>
                <div className="mt-2 text-sm text-[#edf3f6]">
                  <p className="font-medium">{selected.symbol}</p>
                  <p className="mt-1 text-[#dfe8ee]">{selected.price} · {selected.change}</p>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.24em] text-[#8b949e]">WHY IT'S UNUSUAL</p>
                <p className="mt-2 text-sm leading-6 text-[#edf3f6]">{selectedStory?.why_it_matters ?? selected.reason}</p>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.24em] text-[#8b949e]">AI CHANGE STORY</p>
                {selectedStory ? (
                  <div className="mt-2 space-y-2 text-sm leading-6 text-[#edf3f6]">
                    <p>{selectedStory.headline}</p>
                    <ul className="list-disc space-y-1 pl-5">
                      {(selectedStory?.what_changed || selectedStory?.what_changed_summary || []).map((item: string, idx: number) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                    <p className="text-[#9AA6A2]">{selectedStory.ai_explanation}</p>
                  </div>
                ) : (
                  <div className="mt-3 flex items-center gap-2 text-sm text-[#9AA6A2]">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#26312E] border-t-[#00D09C]" />
                    Loading evidence-backed story...
                  </div>
                )}
                <div className="mt-3 rounded-xl border border-[#2a3138] bg-[#0d1418] p-3">
                  <p className="text-[9px] uppercase tracking-[0.2em] text-[#8b949e]">Based on</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-[9px] uppercase tracking-[0.12em] text-[#dfe7eb]">
                    <span className="rounded-full border border-[#2a3138] bg-[#121b20] px-2 py-1">Price movement</span>
                    <span className="rounded-full border border-[#2a3138] bg-[#121b20] px-2 py-1">Volume anomaly</span>
                    <span className="rounded-full border border-[#2a3138] bg-[#121b20] px-2 py-1">Sector comparison</span>
                    <span className="rounded-full border border-[#2a3138] bg-[#121b20] px-2 py-1">Market comparison</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-[9px] uppercase tracking-[0.12em] text-[#dfe7eb]">
                    <span>Confidence</span>
                    <span>91%</span>
                  </div>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.24em] text-[#8b949e]">EVIDENCE</p>
                <div className="mt-3 space-y-2 text-sm text-[#edf3f6]">
                  <div className="flex justify-between"><span>Price</span><span className={getPriceTone(selected.change)}>{selected.change}</span></div>
                  <div className="flex justify-between"><span>Relative Performance</span><span>+3.3%</span></div>
                  <div className="flex justify-between"><span>Volume</span><span>2.8× normal</span></div>
                  <div className="flex justify-between"><span>52-week position</span><span>91%</span></div>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#8b949e]">MCI BREAKDOWN</p>
                <div className="mt-3 space-y-2">
                  {breakdown.map(([label, value]) => (
                    <div key={label}>
                      <div className="mb-1 flex items-center justify-between text-[11px] text-[#dfe7ec]">
                        <span>{label}</span>
                        <span>{value} / 25</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[#6ee7b7] via-[#f7d365] to-[#ff596d]"
                          style={{ width: `${Math.min((value / 25) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-[#2a3138] pt-2 text-sm text-[#edf3f6]">
                  <span>Total</span>
                  <span>{totalBreakdownScore} / 100</span>
                </div>
              </div>

              <div className="rounded-[20px] border border-[#2a3138] bg-[#10171c] p-3">
                <button
                  type="button"
                  onClick={() => setMciExpanded((open) => !open)}
                  className="flex w-full items-center justify-between text-left text-[10px] uppercase tracking-[0.22em] text-[#8b949e]"
                >
                  <span>Why did MCI change?</span>
                  <ChevronRight className={`h-4 w-4 transition ${mciExpanded ? "rotate-90" : ""}`} />
                </button>

                {mciExpanded && (
                  <div className="mt-2 rounded-2xl border border-[#2a3138] bg-[#0d1418] p-2.5 text-sm leading-6 text-[#edf3f6]">
                    <p>Largest contributors</p>
                    <ul className="mt-2 space-y-1 text-[#dfe8ee]">
                      <li>+{selected.mciBreakdown.price} Price movement</li>
                      <li>+{selected.mciBreakdown.volume} Volume anomaly</li>
                      <li>+{selected.mciBreakdown.relative} Relative performance</li>
                      <li>+{selected.mciBreakdown.event} Event signal</li>
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
