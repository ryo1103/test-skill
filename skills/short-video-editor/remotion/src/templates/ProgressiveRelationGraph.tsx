import React from 'react';
import {GraphNode, OpenCanvas, RelationEdge, SceneWash, cueFrameForOrder, pointForNode, useEditorialProgress} from '../components/Editorial';
import {MotionLayerProps} from '.';

export const ProgressiveRelationGraph: React.FC<MotionLayerProps> = (props) => {
  const fps = props.fps || 30;
  const duration = Math.max(16, props.durationInFrames || fps * 2);
  const wash = useEditorialProgress(0, Math.max(8, Math.round(fps * 0.35)));
  const anchors = props.scene?.cueAnchors || [];
  const nodes = props.scene?.nodes?.length ? props.scene.nodes : [
    {id: 'core', label: props.core || props.input || '核心', iconSlot: 'core', role: 'root', position: {x: 0.5, y: 0.16}, revealOrder: 0},
    {id: 'dependency_a', label: props.dependencyA || props.connector || '条件 A', iconSlot: 'dependency_a', role: 'dependency', position: {x: 0.17, y: 0.64}, revealOrder: 1},
    {id: 'dependency_b', label: props.dependencyB || props.output || '条件 B', iconSlot: 'dependency_b', role: 'dependency', position: {x: 0.83, y: 0.64}, revealOrder: 2},
  ];
  const nodeById = Object.fromEntries(nodes.map((node, index) => [node.id, {node, point: pointForNode(node, {x: 0.18 + index * 0.32, y: 0.5})}]));
  const connectors = props.scene?.connectors?.length ? props.scene.connectors : [
    {from: nodes[0].id, to: nodes[1].id, revealOrder: 1},
    {from: nodes[0].id, to: nodes[2].id, revealOrder: 2},
  ];
  const fontFamily = props.styleTokens?.fontFamily;
  return (
    <>
      <SceneWash progress={wash} opacity={0.3} />
      <OpenCanvas>
        {connectors.map((connector) => {
          const source = nodeById[connector.from];
          const target = nodeById[connector.to];
          if (!source || !target) return null;
          const order = Number(connector.revealOrder || target.node.revealOrder || 1);
          const nodeStart = cueFrameForOrder(anchors, order, fps, Math.round(duration * (order === 1 ? 0.32 : 0.58)));
          return <RelationEdge key={`${connector.from}-${connector.to}`} from={source.point} to={target.point} startFrame={Math.max(0, nodeStart - Math.round(duration * 0.1))} durationFrames={Math.max(5, Math.round(duration * 0.18))} color="#f4fbff" curved={props.scene?.topology === 'hub_spoke'} />;
        })}
        {nodes.map((node, index) => {
          const order = Number(node.revealOrder ?? index);
          const fallback = order === 0 ? duration * 0.06 : order === 1 ? duration * 0.32 : duration * 0.58;
          const startFrame = cueFrameForOrder(anchors, order, fps, Math.round(fallback));
          const point = nodeById[node.id]?.point || pointForNode(node, {x: 0.18 + index * 0.32, y: 0.5});
          const iconSlot = node.iconSlot || node.id;
          const accent = node.role === 'root' || node.role === 'cause' ? (props.styleTokens?.accentSecondary || '#ff4f87') : index % 2 ? '#f4fbff' : (props.styleTokens?.accentPrimary || '#19e6e6');
          return <GraphNode key={node.id} node={node} point={point} icon={props.icons?.[iconSlot]} startFrame={startFrame} durationFrames={Math.max(5, Math.round(duration * 0.16))} accent={accent} fontFamily={fontFamily} />;
        })}
      </OpenCanvas>
    </>
  );
};
