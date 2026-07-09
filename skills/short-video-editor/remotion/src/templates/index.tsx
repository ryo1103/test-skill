import React from 'react';
import {AbsoluteFill} from 'remotion';
import {ConceptDefinition} from './ConceptDefinition';
import {ConnectorFlow} from './ConnectorFlow';
import {DensityPressure} from './DensityPressure';
import {MetricGrowth} from './MetricGrowth';
import {NegationToConnector} from './NegationToConnector';
import {NodeRelationTriangle} from './NodeRelationTriangle';
import {ProcessMigration} from './ProcessMigration';
import {SystemErrorPanel} from './SystemErrorPanel';

export type MotionLayerProps = {
  templateId: string;
  motionId?: string;
  semanticAction?: string;
  claim?: string;
  labels?: string[];
  icons?: Record<string, string>;
  style?: string;
  durationInFrames?: number;
  subject?: string;
  rejectedA?: string;
  rejectedB?: string;
  acceptedDefinition?: string;
  input?: string;
  connector?: string;
  output?: string;
  metric?: string;
  baseline?: string;
  targetOrDelta?: string;
  oldStep?: string;
  newStep?: string;
  result?: string;
  oldSolution?: string;
  newRequirement?: string;
  newSolution?: string;
  definition?: string;
  role?: string;
};

export const MotionLayer: React.FC<MotionLayerProps> = (props) => {
  const template = props.templateId;
  return (
    <AbsoluteFill style={{background: 'transparent'}}>
      {template === 'negation_to_connector' && <NegationToConnector {...props} />}
      {template === 'connector_flow' && <ConnectorFlow {...props} />}
      {template === 'metric_growth' && <MetricGrowth {...props} />}
      {template === 'process_migration' && <ProcessMigration {...props} />}
      {template === 'density_pressure' && <DensityPressure {...props} />}
      {template === 'concept_definition' && <ConceptDefinition {...props} />}
      {template === 'system_error_panel' && <SystemErrorPanel {...props} />}
      {template === 'node_relation_triangle' && <NodeRelationTriangle {...props} />}
    </AbsoluteFill>
  );
};
