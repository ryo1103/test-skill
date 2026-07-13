import React from 'react';
import {GraphNode, LocalLabel, OpenCanvas, SceneWash, useEditorialProgress} from '../components/Editorial';
import {MotionIconRef} from '../components/SemanticIcon';
import {MotionLayerProps} from '.';

const RejectedNode: React.FC<{x: number; label: string; progress: number; icon?: MotionIconRef; fontFamily?: string}> = ({x, label, progress, icon, fontFamily}) => (
  <div style={{position: 'absolute', left: x, top: 184, width: 270, height: 238, opacity: progress, transform: `translateY(${(1 - progress) * 26}px)`, fontFamily}}>
    <GraphNode node={{id: label, label, role: 'rejected'}} point={{x: 135, y: 92}} icon={icon} startFrame={0} accent="#ff4f87" fontFamily={fontFamily} />
    <div style={{position: 'absolute', left: 58, top: 94, width: 154 * progress, height: 7, background: '#ff4f87', transform: 'rotate(-35deg)', transformOrigin: 'left center', boxShadow: '0 0 10px rgba(255,79,135,.6)'}} />
  </div>
);

export const NegationToConnector: React.FC<MotionLayerProps> = (props) => {
  const duration = Math.max(16, props.durationInFrames || (props.fps || 30) * 2);
  const acceptedStart = Math.round(duration * 0.54);
  const a = useEditorialProgress(Math.round(duration * 0.04), Math.max(5, Math.round(duration * 0.16)));
  const b = useEditorialProgress(Math.round(duration * 0.25), Math.max(5, Math.round(duration * 0.16)));
  const accepted = useEditorialProgress(acceptedStart, Math.max(6, Math.round(duration * 0.2)));
  const wash = useEditorialProgress(0, 12);
  const fontFamily = props.styleTokens?.fontFamily;
  const acceptedNode = {id: 'accepted', label: props.acceptedDefinition || '重新定义', role: 'accepted'};
  return (
    <>
      <SceneWash progress={wash} opacity={0.25} />
      <OpenCanvas>
        <RejectedNode x={92} label={props.rejectedA || '旧定义 A'} progress={a} icon={props.icons?.rejected_a} fontFamily={fontFamily} />
        <RejectedNode x={598} label={props.rejectedB || '旧定义 B'} progress={b} icon={props.icons?.rejected_b} fontFamily={fontFamily} />
        <GraphNode node={acceptedNode} point={{x: 480, y: 650}} icon={props.icons?.accepted_definition} startFrame={acceptedStart} durationFrames={Math.max(6, Math.round(duration * 0.2))} accent="#72ebcb" fontFamily={fontFamily} />
        <LocalLabel x={326} y={458} accent="#19e6e6" progress={accepted} fontFamily={fontFamily}>{props.subject || '核心概念'}</LocalLabel>
      </OpenCanvas>
    </>
  );
};
