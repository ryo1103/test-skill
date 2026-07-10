import React from 'react';
import {Card, FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const ConceptDefinition: React.FC<MotionLayerProps> = (props) => {
  const subject = useProgress(0, 16);
  const relation = useProgress(12, 24);
  const role = useProgress(28, 18);
  return (
    <Panel accent="#65e7ff">
      <Card x={92} y={150} w={250} h={180} accent="#72ebcb" p={subject}><IconBlock accent="#72ebcb" icon={props.icons?.subject} label={props.subject || '主体'} /></Card>
      <FlowLine x1={332} y={240} w={250} p={relation} />
      <Card x={552} y={150} w={250} h={180} accent="#6eefff" p={role}><IconBlock accent="#6eefff" icon={props.icons?.definition} label={props.definition || '定义'} /></Card>
      <MicroLabel x={446} y={412} text={fit(props.role, '连接作用')} color="#fff" size={30} />
    </Panel>
  );
};
