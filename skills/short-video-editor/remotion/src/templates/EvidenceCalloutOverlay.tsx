import React from 'react';
import {OpenCanvas, SceneWash, useEditorialProgress} from '../components/Editorial';
import {SemanticIcon} from '../components/SemanticIcon';
import {MotionLayerProps} from '.';

export const EvidenceCalloutOverlay: React.FC<MotionLayerProps> = (props) => {
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const header = useEditorialProgress(0, Math.max(5, Math.round(duration * 0.16)));
  const pin = useEditorialProgress(Math.round(duration * 0.24), Math.max(6, Math.round(duration * 0.2)));
  const metric = useEditorialProgress(Math.round(duration * 0.52), Math.max(6, Math.round(duration * 0.2)));
  const wash = useEditorialProgress(0, 12);
  const fontFamily = props.styleTokens?.fontFamily || 'PingFang SC, Arial, sans-serif';
  const subject = props.subject || '关键环节';
  const bottleneck = props.bottleneck || '核心瓶颈';
  const value = props.durationOrMetric || '关键约束';
  return (
    <>
      <SceneWash progress={wash} opacity={0.2} />
      <OpenCanvas>
        <div style={{position: 'absolute', left: 86, top: 72, width: 788, minHeight: 118, opacity: header, transform: `translateY(${(1 - header) * -24}px)`, border: '2px solid #ff4f87', borderLeftWidth: 7, background: 'rgba(8,20,58,.82)', boxShadow: '0 14px 36px rgba(0,0,0,.3)', display: 'flex', alignItems: 'center', padding: '0 34px', color: '#ffffff', fontFamily}}>
          <SemanticIcon icon={props.icons?.bottleneck || props.icons?.subject} color="#ff4f87" size={54} glow />
          <div style={{marginLeft: 24, fontSize: 39, fontWeight: 820}}><span style={{color: '#ff7aa2'}}>{subject}</span><span style={{opacity: .7}}> · </span>{bottleneck}</div>
        </div>
        <svg width="960" height="900" viewBox="0 0 960 900" style={{position: 'absolute', inset: 0}}>
          <path d="M 480 190 L 480 360 L 430 420" fill="none" stroke="#ffffff" strokeOpacity={0.85 * pin} strokeWidth="3" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - pin} strokeLinecap="round" />
          <circle cx="430" cy="420" r={9 + 10 * pin} fill="none" stroke="#ff4f87" strokeWidth="3" opacity={pin} style={{filter: 'drop-shadow(0 0 8px #ff4f87)'}} />
          <circle cx="430" cy="420" r="5" fill="#ffffff" opacity={pin} />
        </svg>
        <div style={{position: 'absolute', left: 190, top: 520, width: 580, minHeight: 238, opacity: metric, transform: `translateY(${(1 - metric) * 28}px) scale(${0.95 + metric * 0.05})`, border: '2px solid rgba(208,232,255,.74)', background: 'rgba(8,24,68,.84)', boxShadow: '0 16px 42px rgba(0,0,0,.34)', textAlign: 'center', color: '#ffffff', fontFamily, padding: '30px 28px'}}>
          <div style={{fontSize: 27, opacity: .76, marginBottom: 10}}>{subject} · {bottleneck}</div>
          <div style={{fontSize: 76, lineHeight: 1.1, fontWeight: 860, letterSpacing: 0}}>{value}</div>
        </div>
      </OpenCanvas>
    </>
  );
};
