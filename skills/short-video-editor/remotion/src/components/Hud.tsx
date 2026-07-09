import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';

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
      border: `6px solid ${accent}`,
      background: 'rgba(2, 13, 22, 0.74)',
      boxShadow: `0 0 42px ${accent}55, inset 0 0 90px rgba(101,231,255,0.12)`,
      overflow: 'hidden',
    }}
  >
    <div style={{position: 'absolute', inset: 18, borderTop: '3px solid rgba(255,255,255,0.22)', borderBottom: '3px solid rgba(255,255,255,0.10)'}} />
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
      border: `4px solid ${accent}`,
      background: 'rgba(5, 20, 32, 0.82)',
      boxShadow: `0 0 28px ${accent}66`,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'white',
      fontFamily: 'PingFang SC, Arial, sans-serif',
      fontWeight: 800,
      textShadow: '0 3px 0 #001018',
    }}
  >
    {children}
  </div>
);

export const MicroLabel: React.FC<{x: number; y: number; text: string; color?: string; size?: number}> = ({x, y, text, color = '#6eefff', size = 24}) => (
  <div style={{position: 'absolute', left: x, top: y, width: 240, marginLeft: -120, textAlign: 'center', color, fontSize: size, fontWeight: 900, fontFamily: 'Arial, sans-serif', textShadow: '0 3px 0 #001018'}}>
    {text}
  </div>
);

export const FlowLine: React.FC<{x1: number; y: number; w: number; p: number; color?: string}> = ({x1, y, w, p, color = '#ffd84f'}) => (
  <div style={{position: 'absolute', left: x1, top: y, width: w * p, height: 12, background: color, boxShadow: `0 0 22px ${color}`, borderRadius: 8}} />
);

export const IconBlock: React.FC<{accent?: string; label?: string}> = ({accent = '#6eefff', label}) => (
  <div style={{width: 82, height: 82, position: 'relative', color: accent}}>
    <div style={{position: 'absolute', left: 10, top: 10, width: 62, height: 62, border: `6px solid ${accent}`}} />
    <div style={{position: 'absolute', left: 32, top: 0, width: 18, height: 82, background: accent, opacity: 0.58}} />
    <div style={{position: 'absolute', left: 0, top: 32, width: 82, height: 18, background: accent, opacity: 0.34}} />
    {label && <div style={{position: 'absolute', left: -50, top: 92, width: 182, textAlign: 'center', color: '#fff', fontSize: 30}}>{fit(label)}</div>}
  </div>
);
