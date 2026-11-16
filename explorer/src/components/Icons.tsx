// Minimal stroke icons (24px grid) so the bundle has no icon dependency.
const P = (d: string) => (props: { size?: number }) => (
  <svg viewBox="0 0 24 24" width={props.size ?? 18} height={props.size ?? 18} fill="none" stroke="currentColor"
    strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
);
export const IconOverview = P("M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z");
export const IconGene = P("M7 3c0 6 10 6 10 12s-10 6-10 6M17 3c0 6-10 6-10 12s10 6 10 6M8 7h8M8 17h8");
export const IconPathway = P("M5 6a2 2 0 1 0 0-.01M19 6a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7 6h10M6.5 7.5l4.5 9M17.5 7.5l-4.5 9");
export const IconMutation = P("M12 3v4M12 17v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M3 12h4M17 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6");
export const IconInteractions = P("M6 7a2 2 0 1 0 0-.01M18 5a2 2 0 1 0 0-.01M18 19a2 2 0 1 0 0-.01M6 17a2 2 0 1 0 0-.01M8 7l8-2M8 17l8 2M6 9v6M18 7v10M8 8l8 10");
export const IconMetabolic = P("M4 12a3 3 0 1 0 6 0 3 3 0 0 0-6 0M14 6a3 3 0 1 0 6 0 3 3 0 0 0-6 0M14 18a3 3 0 1 0 6 0 3 3 0 0 0-6 0M10 11l4-3M10 13l4 3");
export const IconLiterature = P("M4 4h11l5 5v11H4zM15 4v5h5M8 13h8M8 17h6");
export const IconStructure = P("M12 2l9 5v10l-9 5-9-5V7zM12 22V12M21 7l-9 5-9-5");
export const IconSun = P("M12 4V2M12 22v-2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M5.6 18.4l-1.4 1.4M19.8 4.2l-1.4 1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8");
export const IconMoon = P("M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z");
export const IconPlay = P("M7 4l13 8-13 8z");
export const IconPause = P("M7 4h3v16H7zM14 4h3v16h-3z");
export const IconReplay = P("M3 12a9 9 0 1 0 3-6.7M3 3v6h6");
export const IconStepF = P("M5 5l10 7-10 7zM19 5v14");
export const IconStepB = P("M19 5 9 12l10 7zM5 5v14");
export const IconFit = P("M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5");
export const IconDownload = P("M12 3v12M7 10l5 5 5-5M4 21h16");
export const IconSearch = P("M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14M21 21l-5-5");
export const IconExpand = P("M12 5v14M5 12h14");
export const IconScissors = P("M6 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6M8.1 7.9 20 20M8.1 16.1 20 4");
export const IconMenu = P("M4 6h16M4 12h16M4 18h16");
export const IconExternal = P("M14 4h6v6M20 4l-9 9M18 14v6H4V6h6");
export const IconUndo = P("M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-3");
