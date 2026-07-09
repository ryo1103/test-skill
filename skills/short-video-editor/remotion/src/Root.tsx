import React from 'react';
import {Composition} from 'remotion';
import {registerRoot} from 'remotion';
import {MotionLayer, MotionLayerProps} from './templates';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition<MotionLayerProps>
      id="MotionLayer"
      component={MotionLayer}
      durationInFrames={72}
      fps={24}
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

registerRoot(RemotionRoot);

export default RemotionRoot;
