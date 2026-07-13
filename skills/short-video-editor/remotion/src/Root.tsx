import React from 'react';
import {CalculateMetadataFunction, Composition, registerRoot} from 'remotion';
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
        templateId: 'progressive_relation_graph',
        motionId: 'motion',
        style: 'editorial_tech_overlay',
        durationInFrames: 72,
        semanticAction: 'relation_network',
        core: '核心概念',
        dependencyA: '条件 A',
        dependencyB: '条件 B',
        claim: '逻辑关系',
        labels: ['核心', '条件 A', '条件 B'],
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
