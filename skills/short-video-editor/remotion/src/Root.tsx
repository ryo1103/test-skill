import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {registerRoot} from 'remotion';
import {MotionLayer, MotionLayerProps} from './templates';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="MotionLayer"
      component={MotionLayer}
      calculateMetadata={calculateMetadata}
      durationInFrames={72}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={{
        templateId: 'concept_definition',
        motionId: 'motion',
        style: 'tech_hud_glass',
        durationInFrames: 72,
        semanticAction: 'concept_definition',
        subject: 'GlassBridge',
        definition: '光纤连接器',
        role: '连接作用',
        claim: '逻辑关系',
        labels: ['概念', '机制', '结果'],
        icons: {},
      }}
    />
  );
};

export const calculateMetadata: CalculateMetadataFunction<MotionLayerProps> = ({props}) => ({
  durationInFrames: Math.max(1, Math.round(props.durationInFrames || 72)),
  fps: Math.max(1, Math.round(props.fps || 30)),
  width: Math.max(1, Math.round(props.width || 1080)),
  height: Math.max(1, Math.round(props.height || 1920)),
});

registerRoot(RemotionRoot);

export default RemotionRoot;
