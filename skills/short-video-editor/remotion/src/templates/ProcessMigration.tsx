import React from 'react';
import {GraphNode, OpenCanvas, SceneWash, cueFrameForOrder, easeOutCubic, useEditorialProgress} from '../components/Editorial';
import {MotionLayerProps} from '.';

export const ProcessMigration: React.FC<MotionLayerProps> = (props) => {
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const anchors = props.scene?.cueAnchors || [];
  const wash = useEditorialProgress(0, 12);
  const nodes = [
    {id: 'old_step', label: props.oldStep || '旧步骤', iconSlot: 'old_step', role: 'previous', position: {x: 0.14, y: 0.54}, revealOrder: 0},
    {id: 'new_step', label: props.newStep || '新步骤', iconSlot: 'new_step', role: 'current', position: {x: 0.5, y: 0.54}, revealOrder: 1},
    {id: 'result', label: props.result || '结果', iconSlot: 'result', role: 'result', position: {x: 0.86, y: 0.54}, revealOrder: 2},
  ];
  const points = nodes.map((node) => ({x: node.position.x * 960, y: node.position.y * 900}));
  const starts = nodes.map((_, order) => cueFrameForOrder(anchors, order, fps, Math.round(duration * (order === 0 ? 0.06 : order === 1 ? 0.34 : 0.62))));
  const railA = useEditorialProgress(Math.max(0, starts[1] - Math.round(duration * 0.1)), Math.max(6, Math.round(duration * 0.2)));
  const railB = useEditorialProgress(Math.max(0, starts[2] - Math.round(duration * 0.1)), Math.max(6, Math.round(duration * 0.2)));
  return (
    <>
      <SceneWash progress={wash} opacity={0.24} />
      <OpenCanvas>
        <svg width="960" height="900" viewBox="0 0 960 900" style={{position: 'absolute', inset: 0}}>
          <line x1={points[0].x} y1={points[0].y} x2={points[1].x} y2={points[1].y} stroke="rgba(255,255,255,.7)" strokeWidth="3" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - easeOutCubic(railA)} />
          <line x1={points[1].x} y1={points[1].y} x2={points[2].x} y2={points[2].y} stroke="#72ebcb" strokeWidth="3" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - easeOutCubic(railB)} style={{filter: 'drop-shadow(0 0 5px #72ebcb)'}} />
        </svg>
        {nodes.map((node, index) => <GraphNode key={node.id} node={node} point={points[index]} icon={props.icons?.[node.iconSlot]} startFrame={starts[index]} durationFrames={Math.max(5, Math.round(duration * 0.16))} accent={index === 0 ? '#ff4f87' : index === 2 ? '#72ebcb' : '#19e6e6'} fontFamily={props.styleTokens?.fontFamily} />)}
      </OpenCanvas>
    </>
  );
};
