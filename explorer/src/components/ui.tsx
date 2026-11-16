import { motion, AnimatePresence } from "motion/react";
import type { ReactNode } from "react";
import type { Citation, EvidenceCode, Statement } from "../types";
import { EVIDENCE } from "../lib/evidence";
import { IconExternal } from "./Icons";

export function Ev({ code, long }: { code: EvidenceCode; long?: boolean }) {
  return <span className={`badge ev ev-${code}`} title={EVIDENCE[code]?.label}>{long ? EVIDENCE[code]?.short : code}</span>;
}

export function Cites({ items, max = 6 }: { items: Citation[]; max?: number }) {
  if (!items?.length) return null;
  return (
    <span className="row wrap" style={{ gap: 6 }}>
      {items.slice(0, max).map((c) => (
        <a key={`${c.source}:${c.id}`} className="chip" href={c.url} target="_blank" rel="noreferrer" title={c.title}>
          {c.source} {c.id}
        </a>
      ))}
      {items.length > max && <span className="tiny muted">+{items.length - max}</span>}
    </span>
  );
}

export function StatementItem({ s }: { s: Statement }) {
  return (
    <div className="statement">
      <div className="row" style={{ alignItems: "flex-start", gap: 8 }}>
        <Ev code={s.code} />
        <span style={{ flex: 1 }}>{s.text}</span>
      </div>
      {s.citations?.length > 0 && <div style={{ marginTop: 6 }}><Cites items={s.citations} max={4} /></div>}
    </div>
  );
}

export function ExtLink({ href, children }: { href: string; children: ReactNode }) {
  return <a href={href} target="_blank" rel="noreferrer" className="row" style={{ display: "inline-flex", gap: 4 }}>
    {children}<IconExternal size={12} /></a>;
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="section-title">{title}</div>{right}
      </div>
      {children}
    </section>
  );
}

export function FadeSwap({ k, children }: { k: string; children: ReactNode }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div key={k} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export function SourceStatus({ status }: { status: Record<string, string> }) {
  const entries = Object.entries(status ?? {});
  if (!entries.length) return null;
  return (
    <div className="row wrap" style={{ gap: 6 }}>
      {entries.map(([k, v]) => (
        <span key={k} className="chip" title={v} style={{ color: v.startsWith("failed") ? "var(--inh)" : v === "ok" ? undefined : "var(--text-3)" }}>
          {v.startsWith("failed") ? "✕" : v === "ok" ? "✓" : "–"} {k}
        </span>
      ))}
    </div>
  );
}

export function Warnings({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return <div className="stack">{items.map((w, i) => <div key={i} className="callout warn">{w}</div>)}</div>;
}

export function Loading({ label = "Retrieving records" }: { label?: string }) {
  return <div className="loading-veil"><div className="stack" style={{ alignItems: "center" }}><div className="spinner" />
    <span className="small muted">{label}</span></div></div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div className="callout danger">{error instanceof Error ? error.message : String(error)}</div>;
}
