import React from 'react';
import {IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const SplitScreenComparison: React.FC<MotionLayerProps> = (props) => {
  const left = useProgress(0, 18);
  const right = useProgress(10, 18);
  const line = useProgress(18, 16);
  const isDensity = props.semanticAction === 'density_comparison';
  const leftTitle = isDensity ? props.oldSolution || '旧方案' : props.oldStep || '之前';
  const rightTitle = isDensity ? props.newSolution || '新方案' : props.newStep || '之后';
  const axis = isDensity ? props.newRequirement || '更高密度' : props.result || '变化';
  return (
    <Panel accent="#65e7ff">
      <div
        style={{
          position: 'absolute',
          left: 34,
          top: 88,
          width: 410,
          height: 390,
          transform: `translateX(${-(1 - left) * 80}px)`,
          opacity: left,
          borderRadius: 16, background: 'rgba(16,74,154,0.72)', boxShadow: '0 12px 30px rgba(0,0,0,.26)',
        }}
      >
        <MicroLabel x={205} y={210} text={fit(leftTitle, 'Panel A')} color="#ffffff" size={38} />
        <div style={{position: 'absolute', left: 164, top: 110}}><IconBlock accent="#bde6ff" icon={props.icons?.old_solution || props.icons?.old_step || props.icons?.before} /></div>
      </div>
      <div
        style={{
          position: 'absolute',
          left: 444,
          top: 88,
          width: 414,
          height: 390,
          transform: `translateX(${(1 - right) * 80}px)`,
          opacity: right,
          borderRadius: 16, background: 'rgba(106,46,194,0.72)', boxShadow: '0 12px 30px rgba(0,0,0,.26)',
        }}
      >
        <MicroLabel x={207} y={210} text={fit(rightTitle, 'Panel B')} color="#ffffff" size={38} />
        <div style={{position: 'absolute', left: 166, top: 110}}><IconBlock accent="#dec7ff" icon={props.icons?.new_solution || props.icons?.new_step || props.icons?.after} /></div>
      </div>
      <div style={{position: 'absolute', left: 443, top: 88, width: 4, height: 390 * line, background: 'rgba(255,255,255,0.35)'}} />
      <MicroLabel x={446} y={510} text={fit(axis, '对比轴')} color="#d9f8ff" size={28} />
    </Panel>
  );
};
