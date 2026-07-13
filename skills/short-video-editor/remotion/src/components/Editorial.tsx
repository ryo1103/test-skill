import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {MotionIconRef, SemanticIcon} from './SemanticIcon';

export type CueAnchor = {
  cue_id?: string;
  text?: string;
  start_offset_sec?: number;
  end_offset_sec?: number;
  progress?: number;
};

export type EditorialNode = {
  id: string;
  label: string;
  iconSlot?: string;
  role?: string;
  position?: {x: number; y: number};
  revealOrder?: number;
};

export type EditorialConnector = {
  from: string;
  to: string;
  relation?: string;
  style?: string;
  revealOrder?: number;
};

export const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
export const easeOutCubic = (value: number) => 1 - Math.pow(1 - clamp01(value), 3);

export const useEditorialProgress = (startFrame: number, durationFrames = 14) => {
  const frame = useCurrentFrame();
  return easeOutCubic(interpolate(frame, [startFrame, startFrame + Math.max(1, durationFrames)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
};

export const SceneWash: React.FC<{progress?: number; opacity?: number}> = ({progress = 1, opacity = 0.28}) => {
  const visibleProgress = 0.08 + clamp01(progress) * 0.92;
  return <div style={{position: 'absolute', left: 0, right: 0, top: 390, height: 1230, background: `linear-gradient(to bottom, rgba(3, 12, 38, 0) 0%, rgba(3, 12, 38, ${opacity * 0.78 * visibleProgress}) 16%, rgba(3, 12, 38, ${opacity * visibleProgress}) 48%, rgba(3, 12, 38, ${opacity * 0.78 * visibleProgress}) 84%, rgba(3, 12, 38, 0) 100%)`}} />;
};

export const OpenCanvas: React.FC<React.PropsWithChildren> = ({children}) => (
  <div style={{position: 'absolute', left: 60, top: 500, width: 960, height: 900, overflow: 'visible'}}>{children}</div>
);

export const cueFrameForOrder = (anchors: CueAnchor[] | undefined, order: number, fps: number, fallback: number) => {
  if (!anchors?.length || order >= anchors.length) return fallback;
  const anchor = anchors[order];
  const offset = Number(anchor?.start_offset_sec);
  return Number.isFinite(offset) ? Math.max(0, Math.round(offset * fps)) : fallback;
};

export const pointForNode = (node: EditorialNode, fallback: {x: number; y: number}) => ({
  x: clamp01(Number(node.position?.x ?? fallback.x)) * 960,
  y: clamp01(Number(node.position?.y ?? fallback.y)) * 900,
});

export const GraphNode: React.FC<{
  node: EditorialNode;
  point: {x: number; y: number};
  icon?: MotionIconRef;
  startFrame: number;
  durationFrames?: number;
  accent?: string;
  fontFamily?: string;
}> = ({node, point, icon, startFrame, durationFrames = 14, accent = '#ff4f87', fontFamily = 'PingFang SC, Arial, sans-serif'}) => {
  const progress = useEditorialProgress(startFrame, durationFrames);
  const ringScale = 0.84 + progress * 0.16;
  return (
    <div style={{position: 'absolute', left: point.x, top: point.y, width: 220, height: 190, transform: `translate(-50%, -50%) scale(${ringScale})`, opacity: progress}}>
      <div style={{position: 'absolute', left: 42, top: 4, width: 132, height: 132, borderRadius: '50%', border: `2px solid ${accent}`, background: 'rgba(5,18,42,.26)', boxShadow: `0 0 ${12 + 18 * progress}px ${accent}88, inset 0 0 24px ${accent}22`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
        <SemanticIcon icon={icon} color="#ffffff" size={58} opacity={progress} scale={0.9 + progress * 0.1} glow />
      </div>
      <div style={{position: 'absolute', left: -18, top: 148, width: 256, textAlign: 'center', color: '#ffffff', fontFamily, fontWeight: 700, fontSize: 27, lineHeight: 1.18, textShadow: '0 2px 10px rgba(0,0,0,.9)'}}>{String(node.label || '').slice(0, 18)}</div>
    </div>
  );
};

export const RelationEdge: React.FC<{
  from: {x: number; y: number};
  to: {x: number; y: number};
  startFrame: number;
  durationFrames?: number;
  color?: string;
  curved?: boolean;
}> = ({from, to, startFrame, durationFrames = 18, color = '#f4fbff', curved = false}) => {
  const progress = useEditorialProgress(startFrame, durationFrames);
  const distance = Math.max(1, Math.hypot(to.x - from.x, to.y - from.y));
  const inset = Math.min(66, distance * 0.24);
  const unitX = (to.x - from.x) / distance;
  const unitY = (to.y - from.y) / distance;
  const start = {x: from.x + unitX * inset, y: from.y + unitY * inset};
  const end = {x: to.x - unitX * inset, y: to.y - unitY * inset};
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2 - (curved ? 48 : 0);
  const path = curved ? `M ${start.x} ${start.y} Q ${midX} ${midY} ${end.x} ${end.y}` : `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
  const inverse = 1 - progress;
  const pulseX = curved ? inverse * inverse * start.x + 2 * inverse * progress * midX + progress * progress * end.x : start.x + (end.x - start.x) * progress;
  const pulseY = curved ? inverse * inverse * start.y + 2 * inverse * progress * midY + progress * progress * end.y : start.y + (end.y - start.y) * progress;
  return (
    <svg width="960" height="900" viewBox="0 0 960 900" style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
      <path d={path} fill="none" stroke={color} strokeOpacity={0.18 * progress} strokeWidth={8} />
      <path d={path} fill="none" stroke={color} strokeOpacity={0.9} strokeWidth={2.5} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - progress} strokeLinecap="round" style={{filter: `drop-shadow(0 0 5px ${color})`}} />
      {progress > 0.03 && progress < 0.98 ? <circle cx={pulseX} cy={pulseY} r={5} fill="#ffffff" style={{filter: `drop-shadow(0 0 8px ${color})`}} /> : null}
    </svg>
  );
};

export const LocalLabel: React.FC<React.PropsWithChildren<{x: number; y: number; accent?: string; progress?: number; fontFamily?: string}>> = ({x, y, accent = '#19e6e6', progress = 1, fontFamily = 'PingFang SC, Arial, sans-serif', children}) => (
  <div style={{position: 'absolute', left: x, top: y, opacity: progress, transform: `translateY(${(1 - progress) * 18}px)`, padding: '15px 24px', borderLeft: `5px solid ${accent}`, background: 'rgba(4,16,42,.78)', color: '#ffffff', fontFamily, fontWeight: 750, fontSize: 28, lineHeight: 1.2, boxShadow: '0 12px 34px rgba(0,0,0,.28)'}}>{children}</div>
);
