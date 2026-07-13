import React from 'react';
import {useCurrentFrame} from 'remotion';
import {LocalLabel, OpenCanvas, SceneWash, cueFrameForOrder, easeOutCubic, useEditorialProgress} from '../components/Editorial';
import {MotionLayerProps} from '.';

const pathForDirection = (direction?: string) => {
  if (direction === 'decline') return 'M 42 170 C 210 170 300 250 480 330 C 630 398 750 454 918 510';
  if (direction === 'rise_then_plateau') return 'M 42 610 C 190 610 230 430 370 360 C 420 320 450 245 480 215 C 620 208 780 260 918 278';
  return 'M 42 610 C 190 610 230 430 370 360 C 420 310 450 235 480 190 C 650 150 790 96 918 58';
};

export const NarrativeTrendCurve: React.FC<MotionLayerProps> = (props) => {
  const frame = useCurrentFrame();
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const anchors = props.scene?.cueAnchors || [];
  const axisStart = cueFrameForOrder(anchors, 0, fps, 1);
  const curveStart = cueFrameForOrder(anchors, 1, fps, Math.round(duration * 0.16));
  const pivotStart = cueFrameForOrder(anchors, 2, fps, Math.round(duration * 0.5));
  const axis = useEditorialProgress(axisStart, Math.max(5, Math.round(duration * 0.14)));
  const curve = useEditorialProgress(curveStart, Math.max(8, Math.round(duration * 0.4)));
  const pivot = useEditorialProgress(pivotStart, Math.max(5, Math.round(duration * 0.16)));
  const wash = useEditorialProgress(0, 12);
  const direction = props.trendDirection || (String(props.targetOrDelta || '').includes('下降') ? 'decline' : 'rise');
  const path = pathForDirection(direction);
  const startPeriod = props.startPeriod || props.baseline || '现在';
  const pivotPeriod = props.pivotPeriod || '拐点';
  const endPeriod = props.endPeriod || '未来';
  const periods = [startPeriod, '', pivotPeriod, '', endPeriod];
  const fontFamily = props.styleTokens?.fontFamily || 'PingFang SC, Arial, sans-serif';
  const pivotY = direction === 'decline' ? 330 : direction === 'rise_then_plateau' ? 215 : 190;
  const projection = direction === 'rise_then_plateau' ? Math.max(0, Math.min(1, (frame - pivotStart - duration * 0.06) / Math.max(1, duration * 0.28))) : curve;
  return (
    <>
      <SceneWash progress={wash} opacity={0.32} />
      <OpenCanvas>
        <svg width="960" height="760" viewBox="0 0 960 760" style={{position: 'absolute', left: 0, top: 24, overflow: 'visible'}}>
          <line x1="42" y1="650" x2={42 + 876 * axis} y2="650" stroke="rgba(255,255,255,.42)" strokeWidth="2" />
          {[42, 261, 480, 699, 918].map((x, index) => <line key={x} x1={x} y1="638" x2={x} y2="662" stroke="rgba(255,255,255,.82)" strokeWidth="3" opacity={Math.max(0, Math.min(1, axis * 5 - index))} />)}
          <path d={path} fill="none" stroke="#19e6e6" strokeWidth="7" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - curve} style={{filter: 'drop-shadow(0 0 8px #19e6e6)'}} />
          {direction === 'rise_then_plateau' ? <path d="M 480 215 C 620 208 780 260 918 278" fill="none" stroke="#ff4f87" strokeWidth="7" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - easeOutCubic(projection)} style={{filter: 'drop-shadow(0 0 8px #ff4f87)'}} /> : null}
          <circle cx="480" cy={pivotY} r={10 + 5 * pivot} fill="#ffffff" opacity={pivot} style={{filter: 'drop-shadow(0 0 10px #19e6e6)'}} />
        </svg>
        {periods.map((period, index) => period ? <div key={index} style={{position: 'absolute', left: 42 + index * 219 - 70, top: 704, width: 140, textAlign: 'center', color: '#ffffff', opacity: axis, fontFamily, fontWeight: 650, fontSize: 24}}>{period}</div> : null)}
        <div style={{position: 'absolute', left: 315, top: 92, width: 330, color: '#19e6e6', opacity: pivot, transform: `translateY(${(1 - pivot) * 22}px)`, textAlign: 'center', fontFamily, fontWeight: 850, fontSize: 72, textShadow: '0 3px 12px rgba(0,0,0,.9)'}}>{pivotPeriod}</div>
        <LocalLabel x={500} y={pivotY + 30} accent="#19e6e6" progress={pivot} fontFamily={fontFamily}>{props.trendLabel || props.targetOrDelta || props.metric || '趋势变化'}</LocalLabel>
      </OpenCanvas>
    </>
  );
};
