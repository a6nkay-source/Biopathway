// Shapes returned by scripts/bpm/service.py (see bpm/explorer.py).

export type EvidenceCode = "EXP" | "CUR" | "PRED" | "LIT" | "HYP";

export interface Citation { source: string; id: string; url: string; title?: string }

export interface NodeData {
  id: string; label: string; kind: string; focus: boolean;
  members?: string[]; xrefs?: Record<string, unknown>;
}
export interface EdgeData {
  id: string; source: string; target: string; relation: string;
  sign: "+" | "-" | "0"; evidence: string; evidenceCode: EvidenceCode;
  directed: boolean; indirect: boolean; modifiers: string[]; phospho: boolean;
  suspect: boolean; detail: string; scores?: Record<string, number>; citations: Citation[];
}
export interface Elements { nodes: { data: NodeData }[]; edges: { data: EdgeData }[] }

export interface Statement { text: string; evidence: string; code: EvidenceCode; section: string; citations: Citation[] }

export interface PathwayRef {
  source: string; id: string; name: string; url: string; evidence?: string; gene?: string; note?: string;
}

export interface Paper {
  pmid: string; doi?: string; title: string; journal?: string; year?: string; first_author?: string;
  abstract?: string; is_review?: boolean; basis?: string; url: string; evidence?: string;
}

export interface GraphPayload {
  kind: string; query: string; resolved: Record<string, any>;
  elements: Elements; focus: string[];
  full?: { pathway: string; title: string; nodes: { data: NodeData }[]; edges: { data: EdgeData }[] };
  statements: Statement[]; pathways: PathwayRef[]; literature: Paper[];
  warnings: string[]; notes: string[]; source_status: Record<string, string>;
  citations: Citation[]; diagram_note: string; retrieved?: string[];
}

export interface MutationChange {
  event: string; name: string; type: string; status: string;
  normal: { id: string; name: string; url: string } | null;
  evidence: string; code: EvidenceCode; summary: string; pmids: string[];
  participant_genes: string[]; edges: string[]; url: string;
}
export interface MutationPayload {
  gene: string; change: string; variant: any; normal: GraphPayload;
  variant_statements: Statement[];
  reactome: { entities: any[]; sets: any[]; pathways: any[] };
  changes: MutationChange[];
  overlay: { edges: Record<string, { status: string; events: { id: string; name: string }[] }>;
             nodes: Record<string, { status: string; label: string; impaired?: string[] }> };
  downstream: string[]; warnings: string[]; notes: string[]; source_status: Record<string, string>;
}

export interface NodeInfo {
  symbol: string; resolved: any; function: Statement[]; go: Statement[];
  pathways: PathwayRef[]; partners: { symbol: string; code: EvidenceCode; basis: string; scores?: any; citations: Citation[] }[];
  warnings: string[]; source_status: Record<string, string>; literature: Paper[];
}

export interface Scenario { id: string; title: string; view: string; summary: string; op: string; params: Record<string, string>; file: string }
