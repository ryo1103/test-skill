import React from 'react';
import {staticFile} from 'remotion';

export type MotionIconRef = {semanticKey: string; src: string; colorToken?: string};

const fallbackPaths: Record<string, string> = {
  chip: 'M6 6h12v12H6zM9 9h6v6H9zM3 8h3m-3 4h3m-3 4h3m12-8h3m-3 4h3m-3 4h3',
  connector: 'M3 12h5m8 0h5M8 7h8v10H8zM10 9v6m4-6v6',
  warning: 'M12 3 22 20H2zM12 9v5m0 3h.01',
  database: 'M5 5c0 4 14 4 14 0s-14-4-14 0m0 0v14c0 4 14 4 14 0V5',
  generic_concept: 'M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
};

export const SemanticIcon: React.FC<{icon?: MotionIconRef; size?: number; color?: string; opacity?: number; scale?: number; rotation?: number; glow?: boolean}> = ({icon, size = 76, color = '#6eefff', opacity = 1, scale = 1, rotation = 0, glow = false}) => {
  const src = icon?.src && !icon.src.startsWith('/') && !/^https?:/.test(icon.src) ? staticFile(icon.src) : '';
  const fallback = fallbackPaths[icon?.semanticKey || 'generic_concept'] || fallbackPaths.generic_concept;
  const common: React.CSSProperties = {width: size, height: size, opacity, transform: `scale(${scale}) rotate(${rotation}deg)`, color, filter: glow ? `drop-shadow(0 0 10px ${color})` : undefined};
  if (src) return <img src={src} style={{...common, objectFit: 'contain'}} />;
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={common}><path d={fallback} /></svg>;
};
