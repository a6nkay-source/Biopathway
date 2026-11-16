import { Fragment, useEffect, useState } from "react";
import type { EdgeData, NodeData, NodeInfo } from "../types";
import { useApi } from "../lib/hooks";
import { RELATION_LABEL } from "../lib/evidence";
import { Cites, Ev, ErrorBox, ExtLink, FadeSwap, Section, StatementItem, Warnings } from "./ui";
import type { Selection } from "./NetworkCanvas";

const GENE_KINDS = new Set(["gene", "complex"]);

function NodeDetail({ node, onNavigate }: { node: NodeData; onNavigate?: (symbol: string) => void }) {
  const members = node.members?.length ? node.members : GENE_KINDS.has(node.kind) ? [node.label] : [];
  // The label lists the query's focus gene first (e.g. "AKT1/AKT3/AKT2"); open that one.
  const lead = node.label.split(/[/ :]/)[0];
  const initial = members.includes(lead) ? lead : members[0] ?? "";
  const [symbol, setSymbol] = useState(initial);
  useEffect(() => setSymbol(initial), [node.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const isGene = GENE_KINDS.has(node.kind) && !!symbol && !symbol.includes(":");
  const { data, error, loading } = useApi<NodeInfo>(isGene ? "node_info" : null, { symbol });
  const kegg = node.xrefs?.kegg as string | undefined;

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="chip">{node.kind}</span>
          {node.focus && <span className="badge" style={{ color: "#d4a017" }}>query focus</span>}
        </div>
        <h3 style={{ fontSize: 19, marginTop: 8 }}>{isGene ? symbol : node.label}</h3>
        {data?.resolved?.name && <div className="muted small">{data.resolved.name}</div>}
      </div>
      {members.length > 1 && (
        <Section title={node.kind === "complex" ? "Complex components" : `KEGG box: ${members.length} genes drawn as one node`}>
          <div className="row wrap" style={{ gap: 6 }}>
            {members.map((m) => <button key={m} className={`btn ${m === symbol ? "active" : ""}`} style={{ height: 26 }} onClick={() => setSymbol(m)}>{m}</button>)}
          </div>
          <p className="tiny muted" style={{ marginBottom: 0 }}>The relation applies to the box as KEGG draws it, not necessarily to every member equally.</p>
        </Section>
      )}
      {!isGene && (
        <div className="kv">
          {kegg && <><dt>KEGG</dt><dd><ExtLink href={`https://www.kegg.jp/entry/${kegg}`}>{kegg}</ExtLink></dd></>}
          {String(node.xrefs?.reactome ?? "") && <><dt>Reactome</dt><dd><ExtLink href={`https://reactome.org/content/detail/${node.xrefs!.reactome}`}>{String(node.xrefs!.reactome)}</ExtLink></dd></>}
          <dt>Node id</dt><dd className="mono tiny">{node.id}</dd>
        </div>
      )}
      {isGene && loading && <div className="row small muted"><div className="spinner" style={{ width: 16, height: 16 }} /> Loading {symbol}…</div>}
      {isGene && error != null && <ErrorBox error={error} />}
      {isGene && data && (
        <FadeSwap k={symbol}>
          <div className="stack" style={{ gap: 16 }}>
            <dl className="kv">
              <dt>NCBI Gene</dt><dd>{data.resolved?.ncbi_gene_id ? <ExtLink href={`https://www.ncbi.nlm.nih.gov/gene/${data.resolved.ncbi_gene_id}`}>{data.resolved.ncbi_gene_id}</ExtLink> : "—"}</dd>
              <dt>UniProt</dt><dd>{data.resolved?.uniprot ? <ExtLink href={`https://www.uniprot.org/uniprotkb/${data.resolved.uniprot}/entry`}>{data.resolved.uniprot}</ExtLink> : "—"}
                {data.resolved?.uniprot_reviewed === false && <span className="tiny muted"> (unreviewed)</span>}</dd>
              <dt>Location</dt><dd>{data.resolved?.location || "—"}</dd>
              {data.resolved?.aliases?.length > 0 && <><dt>Aliases</dt><dd className="small">{data.resolved.aliases.slice(0, 6).join(", ")}</dd></>}
            </dl>
            {onNavigate && <div className="row wrap" style={{ gap: 6 }}>
              <button className="btn" onClick={() => onNavigate(`gene:${symbol}`)}>Gene explorer</button>
              <button className="btn" onClick={() => onNavigate(`structure:${symbol}`)}>3D structure</button>
              <button className="btn" onClick={() => onNavigate(`interactions:${symbol}`)}>Interactions</button>
            </div>}
            <Warnings items={data.warnings} />
            {data.function.length > 0 && <Section title="Biological function">
              <div className="stack">{data.function.map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>}
            {data.go.length > 0 && <Section title="GO biological process">
              <div className="stack">{data.go.slice(0, 3).map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>}
            {data.partners.length > 0 && <Section title="Interaction partners (STRING)">
              <table className="data"><tbody>{data.partners.slice(0, 10).map((p) => (
                <tr key={p.symbol}><td><b>{p.symbol}</b></td><td><Ev code={p.code} /></td>
                  <td className="mono tiny">{p.scores?.combined?.toFixed?.(3)}</td></tr>))}</tbody></table>
              <p className="tiny muted" style={{ marginBottom: 0 }}>Undirected functional associations; labels come from the strongest single evidence channel.</p>
            </Section>}
            {data.pathways.length > 0 && <Section title={`Pathways (${data.pathways.length})`}>
              <ul className="list">{data.pathways.slice(0, 12).map((p) => (
                <li key={`${p.source}${p.id}`} className="row" style={{ gap: 6 }}><span className="chip">{p.source}</span>
                  <a href={p.url} target="_blank" rel="noreferrer">{p.name}</a></li>))}</ul></Section>}
          </div>
        </FadeSwap>
      )}
    </div>
  );
}

function EdgeDetail({ edge, labelOf }: { edge: EdgeData; labelOf: (id: string) => string }) {
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div>
        <span className="chip">{edge.directed ? "directed relation" : "undirected association"}</span>
        <h3 style={{ fontSize: 17, marginTop: 8, lineHeight: 1.35 }}>
          {labelOf(edge.source)} <span className="muted" style={{ fontWeight: 500 }}>{RELATION_LABEL[edge.relation] ?? edge.relation}</span> {labelOf(edge.target)}
        </h3>
      </div>
      <div className="row wrap"><Ev code={edge.evidenceCode} long />
        {edge.modifiers.map((m) => <span key={m} className="chip">{m}</span>)}
        {edge.indirect && <span className="chip">indirect</span>}</div>
      {edge.suspect && <div className="callout warn">KEGG's own file probably encodes this relation backwards. It is drawn as KEGG records it. Check the direction against Reactome or the literature before relying on it.</div>}
      <Section title="Basis"><p className="small" style={{ margin: 0 }}>{edge.detail}</p></Section>
      {edge.scores && Object.keys(edge.scores).length > 0 && <Section title="STRING channel scores">
        <dl className="kv">{Object.entries(edge.scores).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd className="mono">{Number(v).toFixed(3)}</dd></Fragment>)}</dl></Section>}
      <Section title="Source records"><Cites items={edge.citations} /></Section>
      {!edge.directed && <p className="tiny muted">An association says the two are linked. It does not give direction or say whether the effect is activating or inhibiting.</p>}
    </div>
  );
}

export default function InfoPanel({ sel, labelOf, onNavigate, empty }: {
  sel: Selection; labelOf: (id: string) => string; onNavigate?: (target: string) => void; empty?: React.ReactNode;
}) {
  if (!sel) return <>{empty ?? <div className="muted small">Select a node or relation to see its records.</div>}</>;
  return <FadeSwap k={`${sel.type}:${sel.data.id}`}>
    {sel.type === "node" ? <NodeDetail node={sel.data} onNavigate={onNavigate} /> : <EdgeDetail edge={sel.data} labelOf={labelOf} />}
  </FadeSwap>;
}
