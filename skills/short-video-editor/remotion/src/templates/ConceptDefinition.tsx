import React from 'react';
import {GraphNode, OpenCanvas, RelationEdge, SceneWash, cueFrameForOrder, useEditorialProgress} from '../components/Editorial';
import {MotionLayerProps} from '.';

export const ConceptDefinition: React.FC<MotionLayerProps> = (props) => {
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const anchors = props.scene?.cueAnchors || [];
  const wash = useEditorialProgress(0, 12);
  const nodes = [
    {id: 'subject', label: props.subject || '核心概念', iconSlot: 'subject', role: 'root', position: {x: 0.5, y: 0.2}, revealOrder: 0},
    {id: 'definition', label: props.definition || '定义', iconSlot: 'definition', role: 'definition', position: {x: 0.2, y: 0.67}, revealOrder: 1},
    {id: 'role', label: props.role || '作用', iconSlot: 'role', role: 'role', position: {x: 0.8, y: 0.67}, revealOrder: 2},
  ];
  const points = nodes.map((node) => ({x: node.position.x * 960, y: node.position.y * 900}));
  const starts = nodes.map((_, order) => cueFrameForOrder(anchors, order, fps, Math.round(duration * (order === 0 ? 0.06 : order === 1 ? 0.34 : 0.6))));
  return (
    <>
      <SceneWash progress={wash} opacity={0.25} />
      <OpenCanvas>
        <RelationEdge from={points[0]} to={points[1]} startFrame={Math.max(0, starts[1] - Math.round(duration * 0.1))} durationFrames={Math.max(5, Math.round(duration * 0.18))} color="#f4fbff" curved />
        <RelationEdge from={points[0]} to={points[2]} startFrame={Math.max(0, starts[2] - Math.round(duration * 0.1))} durationFrames={Math.max(5, Math.round(duration * 0.18))} color="#19e6e6" curved />
        {nodes.map((node, index) => <GraphNode key={node.id} node={node} point={points[index]} icon={props.icons?.[node.iconSlot]} startFrame={starts[index]} durationFrames={Math.max(5, Math.round(duration * 0.16))} accent={index === 0 ? '#ff4f87' : index === 2 ? '#19e6e6' : '#f4fbff'} fontFamily={props.styleTokens?.fontFamily} />)}
      </OpenCanvas>
    </>
  );
};
