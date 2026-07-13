import React from 'react';
import {OpenCanvas, SceneWash, useEditorialProgress} from '../components/Editorial';
import {SemanticIcon} from '../components/SemanticIcon';
import {MotionLayerProps} from '.';

export const SplitScreenComparison: React.FC<MotionLayerProps> = (props) => {
  const duration = Math.max(16, props.durationInFrames || (props.fps || 30) * 2);
  const left = useEditorialProgress(Math.round(duration * 0.04), Math.max(6, Math.round(duration * 0.18)));
  const right = useEditorialProgress(Math.round(duration * 0.25), Math.max(6, Math.round(duration * 0.18)));
  const axisIn = useEditorialProgress(Math.round(duration * 0.5), Math.max(5, Math.round(duration * 0.16)));
  const wash = useEditorialProgress(0, 12);
  const isDensity = props.semanticAction === 'density_comparison';
  const leftTitle = isDensity ? props.oldSolution || '旧方案' : props.oldStep || '之前';
  const rightTitle = isDensity ? props.newSolution || '新方案' : props.newStep || '之后';
  const axis = isDensity ? props.newRequirement || '核心差异' : props.result || '变化';
  const fontFamily = props.styleTokens?.fontFamily || 'PingFang SC, Arial, sans-serif';
  const sideStyle: React.CSSProperties = {position: 'absolute', top: 206, width: 398, height: 448, background: 'rgba(5,18,48,.5)', boxShadow: '0 18px 44px rgba(0,0,0,.22)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#fff', fontFamily};
  return (
    <>
      <SceneWash progress={wash} opacity={0.23} />
      <OpenCanvas>
        <div style={{position: 'absolute', left: 350, top: 94, padding: '12px 28px', borderTop: '3px solid #19e6e6', background: 'rgba(4,16,42,.76)', color: '#fff', opacity: axisIn, transform: `translateY(${(1 - axisIn) * 14}px)`, fontFamily, fontWeight: 760, fontSize: 30}}>{axis}</div>
        <div style={{...sideStyle, left: 52, opacity: left, transform: `translateX(${(1 - left) * -48}px)`, borderLeft: '4px solid #ff4f87'}}>
          <SemanticIcon icon={props.icons?.old_solution || props.icons?.old_step || props.icons?.before} color="#ff7aa2" size={74} opacity={left} glow />
          <div style={{marginTop: 32, maxWidth: 330, textAlign: 'center', fontSize: 43, lineHeight: 1.16, fontWeight: 820}}>{leftTitle}</div>
        </div>
        <div style={{...sideStyle, left: 510, opacity: right, transform: `translateX(${(1 - right) * 48}px)`, borderRight: '4px solid #72ebcb'}}>
          <SemanticIcon icon={props.icons?.new_solution || props.icons?.new_step || props.icons?.after} color="#72ebcb" size={74} opacity={right} glow />
          <div style={{marginTop: 32, maxWidth: 330, textAlign: 'center', fontSize: 43, lineHeight: 1.16, fontWeight: 820}}>{rightTitle}</div>
        </div>
        <div style={{position: 'absolute', left: 479, top: 248, width: 2, height: 360 * axisIn, background: 'linear-gradient(transparent, rgba(255,255,255,.72), transparent)'}} />
      </OpenCanvas>
    </>
  );
};
