import React from 'react';
import {FlowLine, IconBlock, MicroLabel, Panel, fit, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

export const NodeRelationTriangle: React.FC<MotionLayerProps> = (props) => {
  const a = useProgress(0, 14);
  const b = useProgress(10, 14);
  const c = useProgress(20, 14);
  const flow = useProgress(28, 22);
  return (
    <Panel accent="#65e7ff">
      <div style={{position: 'absolute', left: 192, top: 178, opacity: a}}><IconBlock accent="#6eefff" icon={props.icons?.cause || props.icons?.input} label={props.input || '原因'} /></div>
      <div style={{position: 'absolute', left: 612, top: 178, opacity: b}}><IconBlock accent="#72ebcb" icon={props.icons?.mechanism || props.icons?.connector} label={props.connector || '机制'} /></div>
      <div style={{position: 'absolute', left: 402, top: 410, opacity: c}}><IconBlock accent="#ffd84f" icon={props.icons?.result || props.icons?.output} label={props.output || props.result || '结果'} /></div>
      <FlowLine x1={300} y={230} w={270} p={flow} />
      <FlowLine x1={330} y={430} w={230} p={flow} color="#72ebcb" />
      <MicroLabel x={446} y={88} text={fit(props.claim, '节点关系')} color="#fff" size={30} />
    </Panel>
  );
};
