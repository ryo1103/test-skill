import React from 'react';
import {Card, FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const ProcessMigration: React.FC<MotionLayerProps> = (props) => {
  const oldP = useProgress(0, 16);
  const trans = useProgress(15, 22);
  const newP = useProgress(30, 18);
  return (
    <Panel accent="#65e7ff">
      <Card x={76} y={142} w={280} h={160} accent="#ff5c7a" p={oldP}><MicroLabel x={216} y={106} text="OLD PATH" color="#ff5c7a" size={20} /><IconBlock accent="#ff5c7a" label={props.oldStep || '旧路径'} /></Card>
      <MicroLabel x={446} y={244} text="TRANSITION" color="#ffd84f" size={22} />
      <FlowLine x1={320} y={322} w={328} p={trans} />
      <Card x={560} y={362} w={280} h={160} accent="#72ebcb" p={newP}><MicroLabel x={700} y={326} text="NEW PATH" color="#72ebcb" size={20} /><IconBlock accent="#72ebcb" label={props.newStep || '新路径'} /></Card>
      <MicroLabel x={690} y={542} text={fit(props.result, '结果')} color="#fff" size={28} />
    </Panel>
  );
};
