import React from 'react';
import {Card, FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const NegationToConnector: React.FC<MotionLayerProps> = (props) => {
  const a = useProgress(0, 14);
  const b = useProgress(8, 14);
  const c = useProgress(18, 18);
  const flow = useProgress(32, 22);
  return (
    <Panel accent="#65e7ff">
      <Card x={70} y={96} w={280} h={190} accent="#ff5c7a" p={a}>
        <IconBlock accent="#ff5c7a" icon={props.icons?.rejected_a} label={props.rejectedA || '芯片'} />
      </Card>
      <Card x={540} y={96} w={280} h={190} accent="#ff5c7a" p={b}>
        <IconBlock accent="#ff5c7a" icon={props.icons?.rejected_b} label={props.rejectedB || '光模块'} />
      </Card>
      <div style={{position: 'absolute', left: 92, top: 170, width: 240 * a, height: 12, background: '#ff5c7a', transform: 'rotate(32deg)', transformOrigin: 'left center'}} />
      <div style={{position: 'absolute', left: 562, top: 170, width: 240 * b, height: 12, background: '#ff5c7a', transform: 'rotate(32deg)', transformOrigin: 'left center'}} />
      <Card x={320} y={328} w={252} h={166} accent="#72ebcb" p={c}>
        <IconBlock accent="#72ebcb" icon={props.icons?.accepted_definition} label={props.acceptedDefinition || '光纤连接器'} />
      </Card>
      <FlowLine x1={160} y={430} w={540} p={flow} />
      <MicroLabel x={446} y={520} text={fit(props.subject, 'GlassBridge')} color="#d9f8ff" size={28} />
    </Panel>
  );
};
