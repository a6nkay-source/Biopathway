import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { motion, AnimatePresence } from "motion/react";
import type { Step } from "../lib/graph";
import type { CanvasHandle } from "./NetworkCanvas";
import { IconPause, IconPlay, IconReplay, IconStepB, IconStepF } from "./Icons";
import { RELATION_LABEL } from "../lib/evidence";
import { Ev } from "./ui";

const BASE_MS = 1100;

export function usePlayback(canvases: RefObject<CanvasHandle | null>[], steps: Step[], sources: string[], reduced: boolean) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const playingRef = useRef(false);
  const idxRef = useRef(0);
  const speedRef = useRef(1);
  speedRef.current = speed;

  const each = (fn: (c: CanvasHandle) => void) => canvases.forEach((c) => c.current && fn(c.current));
  const show = useCallback((i: number) => {
    idxRef.current = i; setIndex(i);
    canvases.forEach((c) => c.current?.showState(steps, i, sources));
  }, [canvases, steps, sources]);

  useEffect(() => {          // new plan: reset
    playingRef.current = false; setPlaying(false); idxRef.current = 0; setIndex(0);
    each((c) => c.clearPlayback());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps]);

  const advance = useCallback(async () => {
    const i = idxRef.current;
    if (i >= steps.length) return false;
    if (i === 0) canvases.forEach((c) => c.current?.showState(steps, 0, sources));
    const ms = (reduced ? 700 : BASE_MS) / speedRef.current;
    await Promise.all(canvases.map((c) => c.current?.animateStep(steps[i], ms, reduced)));
    idxRef.current = i + 1; setIndex(i + 1);
    return true;
  }, [canvases, steps, sources, reduced]);

  const play = useCallback(async () => {
    if (playingRef.current || !steps.length) return;
    if (idxRef.current >= steps.length) show(0);
    playingRef.current = true; setPlaying(true);
    while (playingRef.current && (await advance())) {
      if (reduced) await new Promise((r) => setTimeout(r, 450 / speedRef.current));
    }
    playingRef.current = false; setPlaying(false);
  }, [advance, steps.length, show, reduced]);

  const pause = useCallback(() => { playingRef.current = false; setPlaying(false); }, []);
  const stepForward = useCallback(() => { if (!playingRef.current) void advance(); }, [advance]);
  const stepBack = useCallback(() => { pause(); show(Math.max(0, idxRef.current - 1)); }, [pause, show]);
  const replay = useCallback(() => { pause(); show(0); setTimeout(() => void play(), 60); }, [pause, show, play]);
  const seek = useCallback((i: number) => { pause(); show(i); }, [pause, show]);
  const stop = useCallback(() => { pause(); idxRef.current = 0; setIndex(0); each((c) => c.clearPlayback()); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pause]);
  return { index, playing, speed, setSpeed, play, pause, stepForward, stepBack, replay, seek, stop };
}

export function PlaybackBar({ pb, steps, labelOf, sourceLabel, onPickSource, reduced }: {
  pb: ReturnType<typeof usePlayback>; steps: Step[]; labelOf: (id: string) => string;
  sourceLabel: string; onPickSource?: () => void; reduced: boolean;
}) {
  const cur = pb.index > 0 ? steps[pb.index - 1] : null;
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="playback" style={{ borderTop: 0, padding: 0 }}>
        <div className="row" style={{ gap: 4 }}>
          <button className="icon-btn" onClick={pb.stepBack} disabled={pb.index === 0} title="Step backward" aria-label="Step backward"><IconStepB /></button>
          {pb.playing
            ? <button className="btn primary" onClick={pb.pause} aria-label="Pause"><IconPause /> Pause</button>
            : <button className="btn primary" onClick={() => void pb.play()} disabled={!steps.length} aria-label="Play">
                <IconPlay /> {pb.index > 0 && pb.index < steps.length ? "Resume" : "Play signal"}</button>}
          <button className="icon-btn" onClick={pb.stepForward} disabled={pb.playing || pb.index >= steps.length} title="Step forward" aria-label="Step forward"><IconStepF /></button>
          <button className="icon-btn" onClick={pb.replay} disabled={!steps.length} title="Replay" aria-label="Replay"><IconReplay /></button>
        </div>
        <div className="scrub" role="slider" aria-valuemin={0} aria-valuemax={steps.length} aria-valuenow={pb.index} aria-label="Playback position">
          {steps.map((s, i) => (
            <div key={s.index} title={`${i + 1}. ${labelOf(s.source)} ${RELATION_LABEL[s.relation] ?? s.relation} ${labelOf(s.target)}`}
              className={`tick ${i < pb.index ? "done" : ""} ${s.kind === "inhibit" ? "inh" : ""} ${s.blocked ? "blocked" : ""} ${i === pb.index - 1 ? "cur" : ""}`}
              onClick={() => pb.seek(i + 1)} />
          ))}
        </div>
        <span className="tiny muted mono">{pb.index}/{steps.length}</span>
        <label className="speed">Speed
          <input type="range" min={0.25} max={3} step={0.25} value={pb.speed} onChange={(e) => pb.setSpeed(+e.target.value)} aria-label="Playback speed" />
          <span className="mono">{pb.speed}×</span></label>
      </div>
      <div className="row" style={{ justifyContent: "space-between", gap: 12 }}>
        <div className="step-caption">
          <AnimatePresence mode="wait">
            <motion.span key={cur ? cur.index : -1} initial={{ opacity: 0, x: 6 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.18 }} className="row" style={{ gap: 8 }}>
              {cur ? <>
                <span className="mono tiny muted">step {cur.index + 1} · layer {cur.layer}</span>
                <span><b>{labelOf(cur.source)}</b> {RELATION_LABEL[cur.relation] ?? cur.relation} <b>{labelOf(cur.target)}</b>
                  {cur.phospho && <span className="chip" style={{ marginLeft: 6, color: "var(--phos)" }}>phosphorylation</span>}</span>
                <Ev code={cur.evidenceCode as any} />
                {cur.blocked && <span className="chip" style={{ color: "var(--inh)" }}>✕ {cur.blockReason}</span>}
                {!cur.blocked && cur.firstArrival && cur.netSign !== "?" && <span className="tiny muted">net effect from source: {cur.netSign === "+" ? "activating" : "inhibitory"}</span>}
              </> : <span className="muted">Source: <b>{sourceLabel}</b>{onPickSource && <> · <button className="btn ghost" style={{ height: 22, padding: "0 4px" }} onClick={onPickSource}>use selected node</button></>}</span>}
            </motion.span>
          </AnimatePresence>
        </div>
        <span className="tiny muted" title="Steps follow graph distance over documented relations. No timing or kinetics is implied.">
          order = graph distance, not timing</span>
      </div>
    </div>
  );
}
