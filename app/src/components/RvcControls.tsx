import { useI18n } from '../services/i18n';
import React from 'react';
import manifest from '../../../contracts/engines/rvc.json';
import { EngineParameters } from './EngineParameters';

export const defaultRvcParameters = Object.fromEntries(manifest.parameters.map((parameter) => [parameter.name, parameter.default])) as Record<string, string | number>;

export function RvcControls({ parameters, onParameters, locked }: {
  parameters: Record<string, string | number>;
  onParameters: (parameters: Record<string, string | number>) => void;
  locked: boolean;
}) {
  return <EngineParameters manifest={manifest} parameters={parameters} onParameters={onParameters} locked={locked}/>;
}
