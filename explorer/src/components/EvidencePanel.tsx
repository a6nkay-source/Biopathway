import type { GraphPayload } from "../types";
import { Cites, Section, SourceStatus, StatementItem, Warnings } from "./ui";

export default function EvidencePanel({ data }: { data: GraphPayload }) {
  const groups = new Map<string, typeof data.statements>();
  for (const s of data.statements) groups.set(s.section, [...(groups.get(s.section) ?? []), s]);
  return (
    <div className="stack" style={{ gap: 16 }}>
      <Section title="Sources queried"><SourceStatus status={data.source_status} /></Section>
      <Warnings items={data.warnings} />
      {data.diagram_note && <div className="callout info">{data.diagram_note}</div>}
      {[...groups.entries()].map(([sec, items]) => (
        <Section key={sec} title={sec}><div className="stack">{items.slice(0, 12).map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>
      ))}
      {data.notes.length > 0 && <Section title="Interpretation notes and limits">
        <ul className="list">{data.notes.map((n, i) => <li key={i} className="small muted">{n}</li>)}</ul></Section>}
      {data.pathways.length > 0 && <Section title="Pathway records">
        <ul className="list">{data.pathways.slice(0, 15).map((p, i) => (
          <li key={i} className="row" style={{ gap: 6 }}><span className="chip">{p.source}</span>
            <a href={p.url} target="_blank" rel="noreferrer">{p.id}</a><span className="small">{p.name}</span></li>))}</ul></Section>}
      {data.literature.length > 0 && <Section title="Literature">
        <ul className="list">{data.literature.slice(0, 8).map((p) => (
          <li key={p.pmid} className="small"><span className={`badge ev ev-${p.evidence === "curated database evidence" ? "CUR" : "LIT"}`}>
            {p.evidence === "curated database evidence" ? "CUR" : "LIT"}</span>{" "}
            {p.title} <a href={p.url} target="_blank" rel="noreferrer">PMID:{p.pmid}</a></li>))}</ul>
        <p className="tiny muted">CUR = cited by the curated record. LIT = search hit offered for reading; not used to draw any relation.</p></Section>}
      <Section title={`All cited records (${data.citations.length})`}><Cites items={data.citations} max={40} /></Section>
      {data.retrieved?.[0] && <p className="tiny muted">Retrieved {data.retrieved[0]} UTC.</p>}
    </div>
  );
}
