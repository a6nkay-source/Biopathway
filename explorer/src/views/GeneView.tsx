import { useState } from "react";
import { motion } from "motion/react";
import { scaleLinear } from "d3-scale";
import { max } from "d3-array";
import type { NodeInfo } from "../types";
import { Ev, ErrorBox, ExtLink, Loading, Section, SourceStatus, StatementItem, Warnings } from "../components/ui";
import { useApi, usePrefersReducedMotion } from "../lib/hooks";

interface Expr {
  symbol: string; source_status: Record<string, string>; notes: string[];
  gtex: { dataset: string; unit: string; url: string; tissues: { tissue: string; tpm: number }[] } | null;
  hpa: { tissue_specificity: string; tissue_specific_ntpm: Record<string, string>; cell_type_specificity: string;
    cell_type_specific_ncpm: Record<string, string>; cancer_specificity: string; url: string; licence: string } | null;
  geo: { count: number; query: string; datasets: { accession: string; title: string; type: string; samples: number; url: string }[] } | null;
}
interface Enr {
  genes: string[]; source_status: Record<string, string>; notes: string[];
  reactome: { pathways_found: number; pathways: { id: string; name: string; found: number; total: number; p_value: number; fdr: number; disease: boolean; url: string }[] } | null;
  kegg_shared: { id: string; name: string; genes: string[]; count: number }[];
}

export default function GeneView({ initial }: { initial: string }) {
  const [tab, setTab] = useState<"gene" | "set">("gene");
  const [q, setQ] = useState(initial);
  const [symbol, setSymbol] = useState(initial);
  const [setQ_, setSetQ] = useState("TP53,BBC3,PMAIP1,BAX,CASP9,CASP3");
  const [geneSet, setGeneSet] = useState("TP53,BBC3,PMAIP1,BAX,CASP9,CASP3");
  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100%", minHeight: 0 }}>
      <div className="toolbar">
        <div className="seg"><button className={tab === "gene" ? "on" : ""} onClick={() => setTab("gene")}>Single gene</button>
          <button className={tab === "set" ? "on" : ""} onClick={() => setTab("set")}>Gene set · cross-pathway</button></div>
        {tab === "gene" ? <form className="row" onSubmit={(e) => { e.preventDefault(); setSymbol(q.trim().toUpperCase()); }}>
          <input className="input" style={{ width: 160 }} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Gene symbol" />
          <button className="btn primary">Explore</button></form> :
          <form className="row" onSubmit={(e) => { e.preventDefault(); setGeneSet(setQ_.replace(/\s+/g, "")); }}>
            <input className="input" style={{ width: 320 }} value={setQ_} onChange={(e) => setSetQ(e.target.value)} aria-label="Gene set" />
            <button className="btn primary">Analyse</button></form>}
      </div>
      <div className="view" style={{ position: "relative" }}>
        {tab === "gene" ? <Gene key={symbol} symbol={symbol} /> : <GeneSet key={geneSet} genes={geneSet} />}
      </div>
    </div>
  );
}

function Gene({ symbol }: { symbol: string }) {
  const info = useApi<NodeInfo>("node_info", { symbol });
  const expr = useApi<Expr>("expression", { symbol });
  const reduced = usePrefersReducedMotion();
  const d = info.data;
  const tissues = expr.data?.gtex?.tissues.slice(0, 18) ?? [];
  const x = scaleLinear().domain([0, max(tissues, (t) => t.tpm) ?? 1]).range([0, 100]);
  return (
    <div style={{ padding: 20, display: "grid", gridTemplateColumns: "minmax(0, 1.1fr) minmax(0, 1fr)", gap: 16, maxWidth: 1400 }}>
      {(info.loading || expr.loading) && <Loading />}
      <div className="stack" style={{ gap: 16 }}>
        <div className="card card-pad">
          {info.error != null && <ErrorBox error={info.error} />}
          {d && <div className="stack" style={{ gap: 14 }}>
            <div><h2 style={{ fontSize: 24 }}>{d.resolved?.symbol ?? symbol}</h2><div className="muted">{d.resolved?.name}</div></div>
            <dl className="kv">
              <dt>NCBI Gene</dt><dd>{d.resolved?.ncbi_gene_id && <ExtLink href={`https://www.ncbi.nlm.nih.gov/gene/${d.resolved.ncbi_gene_id}`}>{d.resolved.ncbi_gene_id}</ExtLink>}</dd>
              <dt>UniProt</dt><dd>{d.resolved?.uniprot && <ExtLink href={`https://www.uniprot.org/uniprotkb/${d.resolved.uniprot}/entry`}>{d.resolved.uniprot}</ExtLink>}</dd>
              <dt>Location</dt><dd>{d.resolved?.location}</dd>
              <dt>Aliases</dt><dd className="small">{d.resolved?.aliases?.join(", ")}</dd>
            </dl>
            <SourceStatus status={d.source_status} />
            <Warnings items={d.warnings} />
            <Section title="Function"><div className="stack">{d.function.map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>
            <Section title="GO biological process"><div className="stack">{d.go.slice(0, 3).map((s, i) => <StatementItem key={i} s={s} />)}</div></Section>
          </div>}
        </div>
        {d && <div className="card card-pad"><Section title={`Pathways (${d.pathways.length})`}>
          <table className="data"><tbody>{d.pathways.slice(0, 20).map((p) => (
            <tr key={p.source + p.id}><td><span className="chip">{p.source}</span></td><td><a href={p.url} target="_blank" rel="noreferrer">{p.name}</a></td>
              <td className="mono tiny muted">{p.id}</td></tr>))}</tbody></table></Section></div>}
      </div>
      <div className="stack" style={{ gap: 16 }}>
        <div className="card card-pad">
          <Section title="Tissue expression · GTEx v8 median TPM" right={expr.data?.gtex && <ExtLink href={expr.data.gtex.url}>GTEx</ExtLink>}>
            {expr.error != null && <ErrorBox error={expr.error} />}
            <div className="stack" style={{ gap: 5 }}>
              {tissues.map((t, i) => (
                <div key={t.tissue} className="bar-row">
                  <span className="tiny" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={t.tissue}>{t.tissue}</span>
                  <div className="bar-track"><motion.div className="bar-fill" initial={{ width: reduced ? `${x(t.tpm)}%` : 0 }} animate={{ width: `${x(t.tpm)}%` }}
                    transition={{ delay: reduced ? 0 : i * 0.025, duration: reduced ? 0 : 0.5, ease: [0.22, 1, 0.36, 1] }} /></div>
                  <span className="mono tiny" style={{ textAlign: "right" }}>{t.tpm}</span>
                </div>))}
            </div>
            {expr.data?.gtex && <p className="tiny muted">Top {tissues.length} of {expr.data.gtex.tissues.length} tissues.</p>}
          </Section>
        </div>
        {expr.data?.hpa && <div className="card card-pad"><Section title="Specificity · Human Protein Atlas" right={<ExtLink href={expr.data.hpa.url}>HPA</ExtLink>}>
          <dl className="kv"><dt>Tissue</dt><dd>{expr.data.hpa.tissue_specificity}</dd>
            {Object.keys(expr.data.hpa.tissue_specific_ntpm).length > 0 && <><dt /><dd className="small">{Object.entries(expr.data.hpa.tissue_specific_ntpm).map(([k, v]) => `${k} ${v} nTPM`).join(" · ")}</dd></>}
            <dt>Cell type</dt><dd>{expr.data.hpa.cell_type_specificity}</dd>
            {Object.keys(expr.data.hpa.cell_type_specific_ncpm).length > 0 && <><dt /><dd className="small">{Object.entries(expr.data.hpa.cell_type_specific_ncpm).slice(0, 6).map(([k, v]) => `${k} ${v}`).join(" · ")}</dd></>}
            <dt>Cancer</dt><dd>{expr.data.hpa.cancer_specificity}</dd></dl>
          <p className="tiny muted" style={{ marginBottom: 0 }}>{expr.data.hpa.licence}</p></Section></div>}
        {expr.data?.geo && <div className="card card-pad"><Section title={`GEO datasets mentioning ${symbol} (${expr.data.geo.count.toLocaleString()})`}>
          <ul className="list">{expr.data.geo.datasets.map((g) => <li key={g.accession} className="small">
            <ExtLink href={g.url}>{g.accession}</ExtLink> {g.title} <span className="muted tiny">· {g.type} · {g.samples} samples</span></li>)}</ul></Section></div>}
        {expr.data && <ul className="list">{expr.data.notes.map((n, i) => <li key={i} className="tiny muted">{n}</li>)}</ul>}
      </div>
    </div>
  );
}

function GeneSet({ genes }: { genes: string }) {
  const { data, error, loading } = useApi<Enr>("enrichment", { genes });
  return (
    <div style={{ padding: 20, display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: 16, maxWidth: 1400 }}>
      {loading && <Loading label="Running Reactome over-representation" />}
      {error != null && <ErrorBox error={error} />}
      {data && <>
        <div className="card card-pad"><Section title={`Reactome over-representation (${data.reactome?.pathways_found ?? 0} pathways hit)`}>
          <table className="data"><thead><tr><th>Pathway</th><th>Genes</th><th>FDR</th></tr></thead><tbody>
            {data.reactome?.pathways.slice(0, 20).map((p) => (
              <tr key={p.id}><td><a href={p.url} target="_blank" rel="noreferrer">{p.name}</a>{p.disease && <span className="chip" style={{ marginLeft: 6 }}>disease</span>}</td>
                <td className="mono tiny">{p.found}/{p.total}</td><td className="mono tiny">{p.fdr.toExponential(1)}</td></tr>))}</tbody></table>
        </Section></div>
        <div className="stack" style={{ gap: 16 }}>
          <div className="card card-pad"><Section title="Shared KEGG maps">
            <table className="data"><tbody>{data.kegg_shared.slice(0, 15).map((k) => (
              <tr key={k.id}><td><a href={`https://www.kegg.jp/pathway/${k.id}`} target="_blank" rel="noreferrer">{k.name}</a></td>
                <td className="mono tiny">{k.count}/{data.genes.length}</td><td className="tiny muted">{k.genes.join(", ")}</td></tr>))}</tbody></table>
          </Section></div>
          <SourceStatus status={data.source_status} />
          <ul className="list">{data.notes.map((n, i) => <li key={i} className="tiny muted">{n}</li>)}</ul>
          <div className="callout info small"><Ev code="CUR" /> Over-representation measures shared curated annotation. It does not show that these genes act together in a given cell.</div>
        </div>
      </>}
    </div>
  );
}
