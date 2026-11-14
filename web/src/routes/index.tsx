import { createFileRoute } from "@tanstack/react-router";

const WINDOWS_DOWNLOAD =
  "https://github.com/rustmofficialwork-lab/Jarvis/releases/download/jarvis-latest/JARVIS-Setup-x64.exe";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "JARVIS — Personal AI Assistant" },
      {
        name: "description",
        content: "Download JARVIS, your personal AI desktop assistant for Windows.",
      },
    ],
  }),
  component: Home,
});

function Home() {
  return (
    <main className="min-h-screen bg-[#07111b] text-slate-100">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <a href="/" className="text-xl font-semibold tracking-[0.2em] text-cyan-300">
          JARVIS
        </a>
        <span className="text-xs tracking-[0.18em] text-slate-400">PERSONAL AI ASSISTANT</span>
      </header>
      <section className="mx-auto flex min-h-[70vh] max-w-5xl flex-col justify-center px-6 py-16">
        <p className="mb-5 text-sm font-semibold tracking-[0.25em] text-cyan-300">
          YOUR DESKTOP AI
        </p>
        <h1 className="max-w-3xl text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Meet your personal AI assistant.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-400">
          A focused Windows desktop assistant for conversations, voice commands, reminders,
          memory, and everyday system tasks.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-4">
          <a
            href={WINDOWS_DOWNLOAD}
            className="inline-flex items-center rounded-lg bg-cyan-300 px-6 py-3 font-semibold text-slate-950 transition hover:bg-cyan-200"
          >
            Download for Windows
          </a>
          <a
            href="https://github.com/rustmofficialwork-lab/Jarvis"
            className="inline-flex items-center rounded-lg border border-slate-700 px-6 py-3 font-medium text-slate-200 transition hover:border-cyan-300"
          >
            View source code
          </a>
        </div>
        <p className="mt-5 text-sm text-slate-500">
          Windows installer · Download the latest published build
        </p>
      </section>
      <footer className="mx-auto max-w-5xl border-t border-slate-800 px-6 py-6 text-sm text-slate-500">
        JARVIS · Personal AI Desktop Assistant
      </footer>
    </main>
  );
}
