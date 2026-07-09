import React from 'react';
import {FlowLine, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const MetricGrowth: React.FC<MotionLayerProps> = (props) => {
  const base = useProgress(0, 18);
  const delta = useProgress(14, 24);
  const arrow = useProgress(30, 22);
  return (
    <Panel accent="#65e7ff">
      <MicroLabel x={220} y={112} text={fit(props.metric, '连接规模')} color="#fff" size={34} />
      <div style={{position: 'absolute', left: 160, top: 182, width: 572, height: 46, background: 'rgba(255,255,255,0.12)'}} />
      <div style={{position: 'absolute', left: 160, top: 182, width: 280 * base, height: 46, background: '#72ebcb', boxShadow: '0 0 20px #72ebcb'}} />
      <MicroLabel x={688} y={128} text="BASELINE" color="#72ebcb" size={24} />
      <MicroLabel x={240} y={318} text={fit(props.targetOrDelta, '快速增加')} color="#fff" size={34} />
      <div style={{position: 'absolute', left: 160, top: 388, width: 572, height: 46, background: 'rgba(255,255,255,0.12)'}} />
      <div style={{position: 'absolute', left: 160, top: 388, width: 460 * delta, height: 46, background: '#ffd84f', boxShadow: '0 0 20px #ffd84f'}} />
      <MicroLabel x={688} y={328} text="+72%" color="#ffd84f" size={40} />
      <FlowLine x1={320} y={522} w={280} p={arrow} />
      <div style={{position: 'absolute', left: 588, top: 486, color: '#ffd84f', fontSize: 88, opacity: arrow}}>›</div>
    </Panel>
  );
};
