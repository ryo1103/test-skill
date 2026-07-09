import React from 'react';
import {Card, FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const ConnectorFlow: React.FC<MotionLayerProps> = (props) => {
  const p1 = useProgress(0, 14);
  const p2 = useProgress(8, 14);
  const p3 = useProgress(16, 14);
  const flow = useProgress(18, 28);
  return (
      <Panel accent="#65e7ff">
      <MicroLabel x={446} y={78} text="FLOW THROUGH" color="#72ebcb" size={23} />
      <MicroLabel x={159} y={146} text="INPUT" />
      <MicroLabel x={447} y={146} text="CONNECTOR" />
      <MicroLabel x={735} y={146} text="OUTPUT" />
      <Card x={60} y={202} w={198} h={176} accent="#6eefff" p={p1}><IconBlock accent="#6eefff" label={props.input || '输入'} /></Card>
      <Card x={348} y={202} w={198} h={176} accent="#72ebcb" p={p2}><IconBlock accent="#72ebcb" label={props.connector || '连接器'} /></Card>
      <Card x={636} y={202} w={198} h={176} accent="#6eefff" p={p3}><IconBlock accent="#6eefff" label={props.output || '输出'} /></Card>
      <FlowLine x1={242} y={272} w={410} p={flow} />
      <div style={{position: 'absolute', left: 640, top: 253, fontSize: 60, color: '#ffd84f', opacity: flow}}>›</div>
      <MicroLabel x={446} y={450} text={fit(props.claim, '连接关系')} color="#ffffff" size={28} />
    </Panel>
  );
};
