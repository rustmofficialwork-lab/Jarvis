import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import {
  Image, FileText, Download, Music, Database, Monitor, Network, Trash2, Mail, MessageCircle,
  Gamepad2, Twitter, Facebook, Instagram, Youtube, Joystick, BookOpen, Radio, Bot, Play, Pause,
  FastForward, Rewind, Settings, Wifi, Lock, ChevronRight, ArrowRight, HardDrive, Video, Folder,
} from "lucide-react";
import helmet from "@/assets/helmet.jpg";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "J.A.R.V.I.S. — Holographic Desktop HUD" },
      { name: "description", content: "An Iron Man inspired JARVIS desktop dashboard with live clock, system stats and quick links." },
      { property: "og:title", content: "J.A.R.V.I.S. — Holographic Desktop HUD" },
      { property: "og:description", content: "Iron Man inspired JARVIS HUD with clock, system info and launcher." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Ring({ size, pct, stroke = 8, children }: { size: number; pct: number; stroke?: number; children?: ReactNode }) {
  const r = size / 2 - stroke - 6;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="absolute inset-0 -rotate-90 glow-svg">
        <circle cx={size / 2} cy={size / 2} r={size / 2 - 2} fill="none" stroke="var(--hud)" strokeWidth="1.5" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--hud-dim)" strokeOpacity=".35" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--hud)" strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
        <circle cx={size / 2} cy={size / 2} r={r - stroke - 4} fill="none" stroke="var(--hud)" strokeOpacity=".6" strokeWidth="1" />
      </svg>
      <div className="relative text-center">{children}</div>
    </div>
  );
}

function ArcReactor() {
  return (
    <div className="relative grid h-[300px] w-[300px] place-items-center">
      <svg viewBox="0 0 300 300" className="absolute inset-0 glow-svg animate-spin-slow">
        <circle cx="150" cy="150" r="146" fill="none" stroke="var(--hud)" strokeWidth="2" />
        <circle cx="150" cy="150" r="128" fill="none" stroke="var(--hud)" strokeWidth="18" strokeDasharray="120 20 60 20" strokeOpacity=".85" />
      </svg>
      <svg viewBox="0 0 300 300" className="absolute inset-0 glow-svg animate-spin-rev">
        <circle cx="150" cy="150" r="104" fill="none" stroke="var(--hud)" strokeWidth="10" strokeDasharray="40 10" strokeOpacity=".7" />
        <circle cx="150" cy="150" r="88" fill="none" stroke="var(--hud)" strokeWidth="3" strokeDasharray="2 6" />
      </svg>
      <div className="relative grid h-28 w-28 place-items-center rounded-full bg-hud-glow glow-box animate-core">
        <div className="h-20 w-20 rounded-full border-4 border-background/40 bg-hud" />
      </div>
    </div>
  );
}

const leftLinks = [
  { icon: Image, label: "Images" }, { icon: FileText, label: "Documents" }, { icon: Download, label: "Downloads" },
  { icon: Music, label: "Music" }, { icon: Database, label: "Storage" },
];
const lowerLinks = [{ icon: Monitor, label: "This PC" }, { icon: Network, label: "Network" }, { icon: Trash2, label: "Recycle Bin" }];
const socials = [
  { icon: Mail, label: "gmail" }, { icon: MessageCircle, label: "whatsapp" }, { icon: Gamepad2, label: "discord" },
  { icon: Twitter, label: "twitter" }, { icon: Facebook, label: "facebook" }, { icon: Instagram, label: "instagram" },
  { icon: Youtube, label: "youtube" }, { icon: Joystick, label: "steam" }, { icon: BookOpen, label: "notion" },
  { icon: Radio, label: "spotify" }, { icon: Bot, label: "chatgpt" },
];
const quotes = [
  ["The future is not a gift, it is an achievement."],
  ["Sometimes you gotta run before you can walk."],
  ["I'm not a hero. I'm just a guy who runs a company."],
  ["Genius, billionaire, playboy, philanthropist."],
];

function useClock() {
  const [d, setD] = useState<Date | null>(null);
  useEffect(() => { setD(new Date()); const t = setInterval(() => setD(new Date()), 1000); return () => clearInterval(t); }, []);
  return d;
}

function Index() {
  const d = useClock();
  const time = d ? d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true }) : "--:-- --";
  const [hm, ampm] = time.split(" ");
  const day = d ? d.toLocaleDateString("en-US", { weekday: "long" }) : "";
  const month = d ? d.toLocaleDateString("en-US", { month: "long" }).toLowerCase() : "";
  const date = d ? d.getDate() : "";

  return (
    <main className="relative min-h-screen overflow-hidden bg-background font-body text-hud">
      <img src={helmet} alt="Armored helmet with glowing eye" className="pointer-events-none absolute right-0 top-0 hidden h-full w-[38%] object-cover object-left helmet-fade xl:block" />

      <div className="relative grid gap-6 p-4 lg:grid-cols-[300px_1fr] xl:grid-cols-[300px_1fr_260px] xl:pr-6">
        {/* LEFT COLUMN */}
        <section className="space-y-5 border-l-2 border-hud pl-4">
          <div className="flex items-start gap-3">
            <Ring size={210} pct={68} stroke={14}>
              <div className="font-hud text-2xl font-bold glow-text">{month}</div>
              <div className="font-hud text-5xl font-black glow-text">{date}</div>
            </Ring>
            <div className="mt-2 text-right">
              <div className="font-hud text-xl font-bold glow-text">{hm} <span className="text-sm">{ampm}</span></div>
              <div className="font-hud text-sm">{day}</div>
            </div>
          </div>
          <div className="space-y-2 text-lg font-semibold">
            <div className="flex items-center gap-2"><HardDrive className="h-5 w-5" /> Full Capacity: 457 GB</div>
            <div className="flex items-center gap-2"><Database className="h-5 w-5" /> Free Capacity: 143 GB</div>
            <div className="h-1.5 w-full bg-hud-dim/30"><div className="h-full w-[70%] bg-hud glow-box" /></div>
          </div>
          <div className="flex items-center gap-4">
            <Ring size={140} pct={98} stroke={8}>
              <div className="font-hud text-xl font-bold glow-text">98%</div>
              <div className="text-sm">Battery</div>
            </Ring>
            <div className="flex-1 space-y-2">
              <div className="font-hud text-sm">Power</div>
              <div className="flex gap-3"><Play className="h-5 w-5" /><Pause className="h-5 w-5" /><FastForward className="h-5 w-5" /><Rewind className="h-5 w-5" /></div>
              <Settings className="h-8 w-8 animate-spin-slow glow-svg" />
              <div className="flex h-16 items-end gap-1">
                {Array.from({ length: 10 }).map((_, i) => (
                  <span key={i} className="w-1.5 bg-hud glow-box animate-bar" style={{ height: "100%", animationDelay: `${i * 0.11}s` }} />
                ))}
              </div>
            </div>
          </div>
          <div className="space-y-1">
            <div className="font-hud text-sm">Wireless Status</div>
            <div className="flex items-center gap-2 text-sm"><Wifi className="h-4 w-4" /> Wi-Fi: Connected</div>
            <div className="text-sm">System: 64 Bit Windows</div>
          </div>
          <ul className="space-y-2 text-lg font-semibold">
            {[[FileText, "Documents"], [Image, "Pictures"], [Music, "Music"], [Video, "Videos"]].map(([I, l]) => {
              const Icon = I as typeof FileText;
              return <li key={l as string} className="flex items-center gap-2 border-b border-hud/40 pb-1"><Icon className="h-4 w-4" />{l as string}<ChevronRight className="ml-auto h-4 w-4" /></li>;
            })}
          </ul>
          <div className="flex items-end justify-between gap-4">
            <div className="hud-panel flex flex-1 items-center justify-between p-3">
              <div><div className="text-lg">Encryption</div><div className="font-semibold text-success">Active</div></div>
              <Lock className="h-6 w-6" />
            </div>
            <Ring size={130} pct={16} stroke={10}>
              <div className="font-hud text-lg font-bold glow-text">16%</div>
              <div className="font-hud text-sm">CPU</div>
            </Ring>
          </div>
        </section>

        {/* CENTER */}
        <section className="space-y-6">
          <div className="grid items-center gap-6 md:grid-cols-[160px_1fr_200px]">
            <ul className="space-y-6">
              {leftLinks.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3 border-b border-hud pb-1 text-lg font-semibold glow-text">
                  <span className="grid h-9 w-9 place-items-center rounded-full border border-hud glow-box"><Icon className="h-4 w-4" /></span>{label}
                </li>
              ))}
            </ul>
            <div className="grid place-items-center"><ArcReactor /></div>
            <ul className="space-y-2 border-l-2 border-hud pl-3">
              {socials.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3 border-b border-hud/40 pb-1 text-lg font-semibold">
                  <Icon className="h-5 w-5" />{label}
                  <span className="ml-auto h-4 w-4 rounded-full border-2 border-hud glow-box" />
                </li>
              ))}
            </ul>
          </div>

          <div className="grid gap-6 md:grid-cols-[160px_1fr]">
            <ul className="space-y-6">
              {lowerLinks.map(({ icon: Icon, label }) => (
                <li key={label} className="flex items-center gap-3 border-b border-hud pb-1 text-lg font-semibold glow-text">
                  <span className="grid h-9 w-9 place-items-center rounded-full border border-hud glow-box"><Icon className="h-4 w-4" /></span>{label}
                </li>
              ))}
            </ul>
            <div className="space-y-4 font-hud text-xs uppercase">
              <div className="hud-panel p-4">
                <div className="mb-2 text-sm font-bold glow-text">System Information</div>
                <div className="grid gap-4 sm:grid-cols-3">
                  <div><p className="text-foreground">CPU</p><p>Intel Core i5 3.20 GHz</p><p className="mt-2 text-foreground">RAM</p><p>8.00 GB</p><p className="mt-2 text-foreground">GPU</p><p>NVIDIA GeForce GTX 1650</p></div>
                  <div><p className="text-foreground">Operating System</p><p>Windows 11 Professional</p><p className="mt-2 text-foreground">Architecture</p><p>64-bit</p></div>
                  <div><p className="text-foreground">Uptime</p><p>2:15:32</p><p className="mt-2 text-foreground">Temperature</p><p>CPU 46°C</p><p>GPU 52°C</p></div>
                </div>
              </div>
              <div className="hud-panel grid gap-4 p-4 sm:grid-cols-3">
                <div><p className="mb-1 text-sm text-foreground">Quick Access</p>{["Control Panel", "Device Manager", "Task Manager", "Run", "Settings"].map((x) => <p key={x}>- {x}</p>)}</div>
                <div><p className="mb-1 text-sm text-foreground">Network Details</p>{["ISP : JioFiber", "IP : 192.168.1.100", "Download : 120 Mbps", "Upload : 80 Mbps"].map((x) => <p key={x}>- {x}</p>)}</div>
                <div><p className="mb-1 text-sm text-foreground">System Status</p>{["Battery : 98%", "CPU : 16%", "RAM : 3.4/8.0 GB", "Disk : 68%"].map((x) => <p key={x}>- {x}</p>)}</div>
              </div>
            </div>
          </div>
        </section>

        {/* RIGHT */}
        <section className="relative space-y-5 lg:col-span-2 xl:col-span-1">
          <div className="flex justify-end"><span className="grid h-11 w-11 place-items-center rounded-full border-2 border-hud glow-box"><ArrowRight className="h-5 w-5" /></span></div>
          <div className="flex items-center justify-end gap-3">
            <div className="text-center text-sm">
              <div className="font-hud">CPU Temp</div><div>16°C</div>
              <div className="mt-2">Atmospheric<br />Roughly<br />Clear</div>
            </div>
            <Ring size={150} pct={75} stroke={10}><div className="font-hud text-4xl font-black glow-text">16°</div></Ring>
          </div>
          <div className="border-b border-hud text-right font-hud text-xl glow-text">Jarvis</div>
          <div className="flex h-6 items-center justify-end gap-0.5">
            {Array.from({ length: 30 }).map((_, i) => <span key={i} className="w-0.5 bg-hud animate-bar" style={{ height: "100%", animationDelay: `${(i % 7) * 0.13}s` }} />)}
          </div>
          <div className="space-y-4 border-r-4 border-hud pr-3">
            {quotes.map(([q]) => (
              <blockquote key={q} className="text-sm font-semibold text-foreground">
                “{q}”<div className="text-right text-hud">— Tony Stark</div>
              </blockquote>
            ))}
          </div>
          <div className="flex justify-between">{[0, 1, 2, 3].map((i) => <span key={i} className="h-4 w-4 bg-hud glow-box" />)}</div>
          <div className="flex flex-col items-end gap-4 pt-4 text-center text-sm font-semibold text-foreground">
            <div className="grid place-items-center"><Trash2 className="h-10 w-10 text-hud" />Recycle Bin</div>
            <div className="grid place-items-center"><Folder className="h-10 w-10 text-hud" />This PC<br />(Computer)</div>
          </div>
        </section>
      </div>
    </main>
  );
}
