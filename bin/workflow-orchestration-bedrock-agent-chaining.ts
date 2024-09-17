#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { WorkflowOrchestrationBedrockAgentChainingStack } from '../lib/workflow-orchestration-bedrock-agent-chaining-stack';

const app = new cdk.App();

new WorkflowOrchestrationBedrockAgentChainingStack(app, 'WorkflowOrchestrationBedrockAgentChainingStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
