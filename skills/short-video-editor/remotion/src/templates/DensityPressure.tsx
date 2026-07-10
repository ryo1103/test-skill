import React from 'react';
import {Card, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const DensityPressure: React.FC<MotionLayerProps> = (props) => {
  const left = useProgress(0, 16);
  const pressure = useProgress(14, 18);
  const expand = useProgress(30, 20);
  return (
    <Panel accent="#65e7ff">
      <Card x={72} y={146} w={272} h={292} accent="#6eefff" p={left}><IconBlock accent="#6eefff" icon={props.icons?.old_solution} label={props.oldSolution || 'FAU'} /></Card>
      {[0, 1, 2].map((idx) => <div key={idx} style={{position: 'absolute', left: 372 + idx * 34, top: 176 + idx * 18, width: 14, height: 210 * pressure, background: '#ff5c7a', boxShadow: '0 0 18px #ff5c7a'}} />)}
      <Card x={548} y={174} w={286 + 46 * expand} h={242} accent="#72ebcb" p={expand}><IconBlock accent="#72ebcb" icon={props.icons?.new_solution} label={props.newSolution || 'GlassBridge'} /></Card>
      <MicroLabel x={446} y={460} text={fit(props.newRequirement, '下一代')} color="#ff5c7a" size={28} />
    </Panel>
  );
};
