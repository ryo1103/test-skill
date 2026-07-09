import React from 'react';
import {MicroLabel, Panel, fit, useProgress} from '../components/Hud';
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
          background: 'linear-gradient(135deg, rgba(28,79,168,0.92), rgba(33,95,213,0.88))',
          boxShadow: '0 0 34px rgba(78,171,255,0.36)',
        }}
      >
        <MicroLabel x={205} y={210} text={fit(leftTitle, 'Panel A')} color="#ffffff" size={38} />
        <MicroLabel x={205} y={288} text="CURRENT" color="#bde6ff" size={22} />
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
          background: 'linear-gradient(135deg, rgba(107,34,205,0.92), rgba(139,52,235,0.88))',
          boxShadow: '0 0 34px rgba(174,95,255,0.36)',
        }}
      >
        <MicroLabel x={207} y={210} text={fit(rightTitle, 'Panel B')} color="#ffffff" size={38} />
        <MicroLabel x={207} y={288} text="NEXT" color="#dec7ff" size={22} />
      </div>
      <div style={{position: 'absolute', left: 443, top: 88, width: 4, height: 390 * line, background: 'rgba(255,255,255,0.35)'}} />
      <div style={{position: 'absolute', left: 34, top: 478, width: 824, height: 126, background: 'rgba(4, 10, 18, 0.78)'}} />
      <MicroLabel x={180} y={510} text="SPLIT SCREEN" color="#ffffff" size={30} />
      <MicroLabel x={492} y={516} text={fit(axis, '对比轴')} color="#86c7ff" size={28} />
      <div style={{position: 'absolute', left: 72, top: 530, width: 14, height: 14, borderRadius: 8, background: '#d6cb54'}} />
    </Panel>
  );
};
