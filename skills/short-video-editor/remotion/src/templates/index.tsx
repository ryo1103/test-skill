import React from 'react';
import {AbsoluteFill} from 'remotion';
import {ConceptDefinition} from './ConceptDefinition';
import {ConnectorFlow} from './ConnectorFlow';
import {DensityPressure} from './DensityPressure';
import {MetricGrowth} from './MetricGrowth';
import {NegationToConnector} from './NegationToConnector';
import {NodeRelationTriangle} from './NodeRelationTriangle';
import {ProgressiveRelationGraph} from './ProgressiveRelationGraph';
import {NarrativeTrendCurve} from './NarrativeTrendCurve';
import {EvidenceCalloutOverlay} from './EvidenceCalloutOverlay';
import {ProcessMigration} from './ProcessMigration';
import {SplitScreenComparison} from './SplitScreenComparison';
import {SystemErrorPanel} from './SystemErrorPanel';
import {MotionIconRef} from '../components/SemanticIcon';

export type MotionLayerProps = {
  templateId: string;
  motionId?: string;
  semanticAction?: string;
  claim?: string;
  labels?: string[];
  fps?: number;
  width?: number;
  height?: number;
  icons?: Record<string, MotionIconRef>;
  scene?: {
    nodes?: Array<{id: string; label: string; iconSlot?: string; role?: string; position?: {x: number; y: number}; revealOrder?: number}>;
    metrics?: Array<{id: string; label: string; value: string; role?: string}>;
    connectors?: Array<{from: string; to: string; style?: string; relation?: string; revealOrder?: number}>;
    cueAnchors?: Array<{cue_id?: string; text?: string; start_offset_sec?: number; end_offset_sec?: number; progress?: number}>;
    intensity?: string;
    layoutType?: string;
    topology?: string;
  };
  styleTokens?: {accentPrimary?: string; accentSecondary?: string; positive?: string; danger?: string; textPrimary?: string; textSecondary?: string; panel?: string; panelEdge?: string; fontFamily?: string};
  timing?: {enterEnd?: number; buildEnd?: number; emphasisEnd?: number; holdEnd?: number};
  style?: string;
  compositionMode?: string;
  backgroundTreatment?: string;
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
  core?: string;
  dependencyA?: string;
  dependencyB?: string;
  startPeriod?: string;
  pivotPeriod?: string;
  endPeriod?: string;
  trendLabel?: string;
  trendDirection?: string;
  bottleneck?: string;
  durationOrMetric?: string;
};

export const MotionLayer: React.FC<MotionLayerProps> = (props) => {
  const template = props.templateId;
  return (
    <AbsoluteFill style={{background: 'transparent'}}>
      {template === 'negation_to_connector' && <NegationToConnector {...props} />}
      {template === 'connector_flow' && <ConnectorFlow {...props} />}
      {template === 'metric_growth' && <MetricGrowth {...props} />}
      {template === 'process_migration' && <ProcessMigration {...props} />}
      {template === 'split_screen_comparison' && <SplitScreenComparison {...props} />}
      {template === 'density_pressure' && <DensityPressure {...props} />}
      {template === 'concept_definition' && <ConceptDefinition {...props} />}
      {template === 'system_error_panel' && <SystemErrorPanel {...props} />}
      {template === 'node_relation_triangle' && <NodeRelationTriangle {...props} />}
      {template === 'progressive_relation_graph' && <ProgressiveRelationGraph {...props} />}
      {template === 'narrative_trend_curve' && <NarrativeTrendCurve {...props} />}
      {template === 'evidence_callout_overlay' && <EvidenceCalloutOverlay {...props} />}
    </AbsoluteFill>
  );
};
