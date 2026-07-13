import React from 'react';
import {GraphNode, OpenCanvas, RelationEdge, SceneWash, cueFrameForOrder, useEditorialProgress} from '../components/Editorial';
import {MotionLayerProps} from '.';

export const ConnectorFlow: React.FC<MotionLayerProps> = (props) => {
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const anchors = props.scene?.cueAnchors || [];
  const wash = useEditorialProgress(0, 12);
  const nodes = [
    {id: 'input', label: props.input || '输入', iconSlot: 'input', role: 'source', position: {x: 0.15, y: 0.48}, revealOrder: 0},
    {id: 'connector', label: props.connector || '连接器', iconSlot: 'connector', role: 'mechanism', position: {x: 0.5, y: 0.48}, revealOrder: 1},
    {id: 'output', label: props.output || '输出', iconSlot: 'output', role: 'result', position: {x: 0.85, y: 0.48}, revealOrder: 2},
  ];
  const points = nodes.map((node) => ({x: node.position.x * 960, y: node.position.y * 900}));
  const starts = nodes.map((_, order) => cueFrameForOrder(anchors, order, fps, Math.round(duration * (order === 0 ? 0.06 : order === 1 ? 0.34 : 0.62))));
  return (
    <>
      <SceneWash progress={wash} opacity={0.24} />
      <OpenCanvas>
        <RelationEdge from={points[0]} to={points[1]} startFrame={Math.max(0, starts[1] - Math.round(duration * 0.1))} durationFrames={Math.max(5, Math.round(duration * 0.18))} color="#19e6e6" />
        <RelationEdge from={points[1]} to={points[2]} startFrame={Math.max(0, starts[2] - Math.round(duration * 0.1))} durationFrames={Math.max(5, Math.round(duration * 0.18))} color="#72ebcb" />
        {nodes.map((node, index) => <GraphNode key={node.id} node={node} point={points[index]} icon={props.icons?.[node.iconSlot]} startFrame={starts[index]} durationFrames={Math.max(5, Math.round(duration * 0.16))} accent={index === 1 ? '#ff4f87' : index === 2 ? '#72ebcb' : '#19e6e6'} fontFamily={props.styleTokens?.fontFamily} />)}
      </OpenCanvas>
    </>
  );
};
