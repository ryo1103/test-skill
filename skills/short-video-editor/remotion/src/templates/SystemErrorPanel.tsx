import React from 'react';
import {Card, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const SystemErrorPanel: React.FC<MotionLayerProps> = (props) => {
  const alert = useProgress(0, 12);
  const trace = useProgress(12, 24);
  const fix = useProgress(34, 18);
  return (
    <Panel accent="#ff5c7a">
      <MicroLabel x={446} y={82} text="SYSTEM ALERT" color="#ff5c7a" size={32} />
      <Card x={112} y={160} w={668} h={90} accent="#ff5c7a" p={alert}><span>{fit(props.input || props.claim, '异常')}</span></Card>
      <div style={{position: 'absolute', left: 160, top: 300, width: 560 * trace, height: 12, background: '#ffd84f'}} />
      <div style={{position: 'absolute', left: 160, top: 348, width: 420 * trace, height: 12, background: '#72ebcb'}} />
      <Card x={250} y={420} w={392} h={104} accent="#72ebcb" p={fix}><span>{fit(props.output || props.result, '恢复')}</span></Card>
    </Panel>
  );
};
