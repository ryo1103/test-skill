import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import {MotionIconRef, SemanticIcon} from './SemanticIcon';

export const fit = (value?: string, fallback = '概念') => String(value || fallback).slice(0, 14);

export const useProgress = (delay = 0, duration = 24) => {
  const frame = useCurrentFrame();
  return Math.max(0, Math.min(1, interpolate(frame - delay, [0, duration], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})));
};

export const Panel: React.FC<React.PropsWithChildren<{x?: number; y?: number; w?: number; h?: number; accent?: string}>> = ({x = 94, y = 690, w = 892, h = 604, accent = '#65e7ff', children}) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      background: 'transparent', overflow: 'visible',
    }}
  >
    {children}
  </div>
);

export const Card: React.FC<React.PropsWithChildren<{x: number; y: number; w: number; h: number; accent?: string; p?: number}>> = ({x, y, w, h, accent = '#6ef0d2', p = 1, children}) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      opacity: p,
      transform: `translateY(${(1 - p) * 24}px) scale(${0.96 + p * 0.04})`,
      border: 'none', borderRadius: 14, background: 'rgba(3, 17, 29, 0.58)',
      boxShadow: `0 10px 28px rgba(0,0,0,0.24), inset 0 1px 0 ${accent}55`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontFamily: 'PingFang SC, Arial, sans-serif',
      fontWeight: 800,
      textShadow: '0 2px 8px rgba(0,0,0,0.72)',
    }}
  >
    {children}
  </div>
);

export const MicroLabel: React.FC<{x: number; y: number; text: string; color?: string; size?: number}> = ({x, y, text, color = '#6eefff', size = 24}) => (
  <div style={{position: 'absolute', left: x, top: y, width: 280, marginLeft: -140, textAlign: 'center', color, fontSize: size, fontWeight: 700, fontFamily: 'PingFang SC, Helvetica Neue, Arial, sans-serif', textShadow: '0 2px 8px rgba(0,0,0,0.72)'}}>
    {text}
  </div>
);

export const FlowLine: React.FC<{x1: number; y: number; w: number; p: number; color?: string}> = ({x1, y, w, p, color = '#6eefff'}) => (
  <div style={{position: 'absolute', left: x1, top: y, width: w * p, height: 4, background: color, boxShadow: `0 0 12px ${color}`, borderRadius: 6}} />
);

export const IconBlock: React.FC<{accent?: string; label?: string; icon?: MotionIconRef}> = ({accent = '#6eefff', label, icon}) => (
  <div style={{width: 82, height: 82, position: 'relative', color: accent}}>
    <SemanticIcon icon={icon} color={accent} size={82} glow />
    {label && <div style={{position: 'absolute', left: -58, top: 92, width: 198, textAlign: 'center', color: '#fff', fontSize: 28, fontFamily: 'PingFang SC, sans-serif', fontWeight: 700, textShadow: '0 2px 8px rgba(0,0,0,.7)'}}>{fit(label)}</div>}
  </div>
);
