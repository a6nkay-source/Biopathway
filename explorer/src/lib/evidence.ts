import type { EvidenceCode } from "../types";

export const EVIDENCE: Record<EvidenceCode, { label: string; color: string; dark: string; short: string }> = {
  EXP: { label: "experimentally validated", color: "#1b7837", dark: "#4ade80", short: "Experimental" },
  CUR: { label: "curated database evidence", color: "#2166ac", dark: "#60a5fa", short: "Curated" },
  PRED: { label: "computationally predicted", color: "#c2410c", dark: "#fb923c", short: "Predicted" },
  LIT: { label: "literature-supported association", color: "#7e22ce", dark: "#c084fc", short: "Literature" },
  HYP: { label: "hypothetical / insufficiently established", color: "#6b7280", dark: "#9ca3af", short: "Hypothetical" },
};
export const CODES: EvidenceCode[] = ["EXP", "CUR", "PRED", "LIT", "HYP"];

export const RELATION_LABEL: Record<string, string> = {
  activation: "activates", inhibition: "inhibits", expression: "induces expression of",
  binding: "binds", association: "is associated with", conversion: "is converted to",
  phosphorylation: "phosphorylates", "pathway link": "links to pathway", contains: "contains",
  "participates in": "participates in", modification: "modifies", "indirect effect": "acts indirectly on",
};

export function evidenceColor(code: EvidenceCode, dark: boolean): string {
  return dark ? EVIDENCE[code].dark : EVIDENCE[code].color;
}
