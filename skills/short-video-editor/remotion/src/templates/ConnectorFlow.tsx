import React from 'react';
import {IconBlock, Panel, useProgress} from '../components/Hud';
import {MotionLayerProps} from '.';

const LinkTrack: React.FC<{x: number; y: number; width: number; progress: number; color: string}> = ({x, y, width, progress, color}) => {
  const pulseX = Math.max(0, width * progress - 9);
  return (
    <div style={{position: 'absolute', left: x, top: y, width, height: 16}}>
      <div style={{position: 'absolute', left: 0, top: 7, width, height: 2, background: 'rgba(190,236,247,.18)'}} />
      <div style={{position: 'absolute', left: 0, top: 6, width: width * progress, height: 4, borderRadius: 4, background: color, boxShadow: `0 0 10px ${color}88`}} />
      {progress > 0 && progress < 1 && <div style={{position: 'absolute', left: pulseX, top: 2, width: 12, height: 12, borderRadius: 8, background: '#fff', boxShadow: `0 0 14px ${color}`}} />}
    </div>
  );
};

export const ConnectorFlow: React.FC<MotionLayerProps> = (props) => {
  const inputIn = useProgress(0, 14);
  const firstLink = useProgress(10, 18);
  const connectorIn = useProgress(18, 14);
  const secondLink = useProgress(28, 18);
  const outputIn = useProgress(38, 14);
  const surfaceIn = useProgress(0, 18);
  const accent = props.styleTokens?.accentPrimary || '#6eefff';
  const secondary = props.styleTokens?.accentSecondary || '#72ebcb';
  return (
    <Panel>
      <div style={{position: 'absolute', left: 48, top: 126, width: 796, height: 236, borderRadius: 24, opacity: .72 * surfaceIn, background: 'rgba(2,16,27,.62)', backdropFilter: 'blur(10px)', boxShadow: '0 18px 42px rgba(0,0,0,.22)'}} />
      <div style={{position: 'absolute', left: 88, top: 196, opacity: inputIn, transform: `scale(${.9 + .1 * inputIn})`}}><IconBlock accent={accent} icon={props.icons?.input} label={props.input || '输入'} /></div>
      <LinkTrack x={184} y={231} width={198} progress={firstLink} color={accent} />
      <div style={{position: 'absolute', left: 405, top: 196, opacity: connectorIn, transform: `scale(${.9 + .1 * connectorIn})`}}><IconBlock accent={secondary} icon={props.icons?.connector} label={props.connector || '连接器'} /></div>
      <LinkTrack x={501} y={231} width={198} progress={secondLink} color={secondary} />
      <div style={{position: 'absolute', left: 722, top: 196, opacity: outputIn, transform: `scale(${.9 + .1 * outputIn})`}}><IconBlock accent={accent} icon={props.icons?.output} label={props.output || '输出'} /></div>
    </Panel>
  );
};
