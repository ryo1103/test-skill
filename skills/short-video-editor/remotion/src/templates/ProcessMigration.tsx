import React from 'react';
import {Card, FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const ProcessMigration: React.FC<MotionLayerProps> = (props) => {
  const oldP = useProgress(0, 16);
  const trans = useProgress(15, 22);
  const newP = useProgress(30, 18);
  return (
    <Panel accent="#65e7ff">
      <Card x={88} y={156} w={230} h={180} accent="#ff5c7a" p={oldP}><IconBlock accent="#ff5c7a" icon={props.icons?.old_step} label={props.oldStep || '旧路径'} /></Card>
      <FlowLine x1={320} y={246} w={244} p={trans} />
      <Card x={570} y={300} w={230} h={180} accent="#72ebcb" p={newP}><IconBlock accent="#72ebcb" icon={props.icons?.new_step} label={props.newStep || '新路径'} /></Card>
      <MicroLabel x={685} y={510} text={fit(props.result, '结果')} color="#d9f8ff" size={26} />
    </Panel>
  );
};
