import { Duration, Stack, StackProps, RemovalPolicy } from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as fs from 'fs';
import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { Bucket } from 'aws-cdk-lib/aws-s3';
import { BucketDeployment, Source} from 'aws-cdk-lib/aws-s3-deployment';
import { PythonFunction} from '@aws-cdk/aws-lambda-python-alpha';
import {Code, Function, Runtime} from 'aws-cdk-lib/aws-lambda';
import { Role, ServicePrincipal, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { bedrock } from '@cdklabs/generative-ai-cdk-constructs';
import { ManagedPolicy } from 'aws-cdk-lib/aws-iam';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as targets from "aws-cdk-lib/aws-elasticloadbalancingv2-targets";
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as ses from 'aws-cdk-lib/aws-ses';
import * as iam from 'aws-cdk-lib/aws-iam';



export class WorkflowOrchestrationBedrockAgentChainingStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const LoanAutomationAndNotificationAgentInstruction = `You are DigiDhan, an advanced AI lending assistant designed to provide personal loan-related information create loan application. Always ask for relevant information and avoid making assumptions. If you're unsure about something, clearly state "I don't have that information."

Always Greet the user by saying the following : Hi there! I am DigiDhan bot. I can help you with loans over this chat. To apply for a loan, kindly provide your full name, PAN Number, email, and the loan amount."

When a user expresses interest in applying for a loan, follow these steps in order, always ask user for necessary details:
1. Determine user status: Identify if they're an existing or new customer.
2. User greetingc(mandatory, do not skip): After determining user status, welcome returning users using following format:
        Existing customer: Hi {customerName}, I see you are an existing customer. Please upload your PAN for KYC
        New customer: Hi {customerName}, I see you are a new customer. Please upload your PAN and Aadhar for KYC
3. Call Pan Verification step using the uploaded PAN document
4. Call Aadhaar Verification step using the uploaded Aadhaar document .Request the user to upload their Aadhaar card document for verification.
5. Loan application: Collect all necessary details to create the loan application.
6. If loan is approved  (email will be sent on details):
	for existing customers: If the loan officer approves the application, inform the user that their loan application has been approved using following format : Congratulations {customerName} your loan is sanctioned. Based on your PAN {pan}, your risk score is {riskScore} and overall credit score is {cibilScore}. I have created your loan application id is {loanId}. The details are mailed to your email.
           for new customers: If the loan officer approves the application, inform the user that their loan application has been approved using following format : Congratulations {customerName} your loan is sanctioned. Based on your PAN {pan} and {aadhar}, your risk score is {riskScore} and overall credit score is {cibilScore}. I have created your loan application id is {loanId}. The details are mailed to your email.
7. If loan is rejected ( no emails sent):
	        for new customers: If the loan officer rejects the application, inform the user that their loan application has been rejected using following format: Hello {customerName} Based on your PAN {pan} and aadhar {aadhar},your overall credit score is {cibilScore}. Due to low credit score, unfortunately your loan application cannot be processed.
            for existing customers: If the loan officer rejects the application, inform the user that their loan application has been rejected using following format: Hello {customerName} Based on your PAN {pan}, your overall credit score is {creditScore}. Due to low credit score, unfortunately your loan application cannot be processed.

Remember to maintain a friendly, professional tone and prioritize the user's needs and concerns throughout the interaction. Be short and direct in your responses, and avoid making assumptions unless specifically requested by the user.

Be short and prompt in responses`

    // Create S3 buckets
    const identityProofImagesBucket = new s3.Bucket(this, 'IdentityProofImagesBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    const loanPolicyDocsBucket = new s3.Bucket(this, 'LoanPolicyDocsBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    const uiHtmlBucket = new s3.Bucket(this, 'HtmlBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });


    new cdk.CfnOutput(this, 'IdentityProofDocumentsBucketName', { value: identityProofImagesBucket.bucketName });
    new cdk.CfnOutput(this, 'loanPolicyDocsBucket', { value: loanPolicyDocsBucket.bucketName });


    // Lambda Roles


    const invokeLoanCreationAgentlambdaFunctionRole = new Role(this, 'invokeLoanCreationAgentlambdaFunctionRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    const createloansLambdaFunctionRole = new Role(this, 'createloansLambdaFunctionRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    // Loan Enquiry Lambda Function
    const loanEnquiryLambdaFunction = new lambda.Function(this, 'LoanEnquiryLambdaFunction', {
      runtime: lambda.Runtime.PYTHON_3_10,
      handler: 'index.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'actions', 'create_loan_enquiry')),
      timeout: Duration.seconds(600),
      role: createloansLambdaFunctionRole,
      environment: {
        'PROOF_IMAGE_SUBMITTED_BUCKET': identityProofImagesBucket.bucketName
      },
      layers: [lambda.LayerVersion.fromLayerVersionArn(this, 'BedrockLayer', 'arn:aws:lambda:us-east-1:770693421928:layer:Klayers-p310-Pillow:8')]
    });

     // Output the Lambda function name and ARN
    new cdk.CfnOutput(this, 'LoanEnquiryLambdaFunctionName', {
      value: loanEnquiryLambdaFunction.functionName,
      description: 'The name of the loan enquiry Lambda function',
    });

    // Create the Loan approval and Notification Agent
    const LoanAutomationAndNotificationAgent = new bedrock.Agent(this, "loanAutomationAndNotificationAgent", {
      name: 'LoanAutomationAndNotificationAgent',
      instruction: LoanAutomationAndNotificationAgentInstruction,
      foundationModel: bedrock.BedrockFoundationModel.ANTHROPIC_CLAUDE_SONNET_V1_0,
      description: 'LoanAutomationAndNotificationAgent',
      idleSessionTTL: Duration.minutes(6),
      shouldPrepareAgent: true
    });

    // Loan Creation Action Group
    const LoanCreationActionGroup = new bedrock.AgentActionGroup(this, 'LoanCreationActionGroup', {
      actionGroupName: 'LoanCreationActionGroup',
      description: 'Action group for loan creation',
      actionGroupExecutor: {
        lambda: loanEnquiryLambdaFunction,
      },
      actionGroupState: 'ENABLED',
      apiSchema: bedrock.ApiSchema.fromAsset(
        path.join(__dirname, '..', './actions/create_loan_enquiry/createloanenquiry_spec.json')
      ),
    });

    LoanAutomationAndNotificationAgent.addActionGroup(LoanCreationActionGroup);


    // Store Agent ID in SSM
    new ssm.StringParameter(this, 'LoanCreationNotificationAgentIdSSM', {
      parameterName: '/loanassit/loanCreationNotificationAgentId',
      stringValue: LoanAutomationAndNotificationAgent.agentId,
    });

    //Output
    new cdk.CfnOutput(this, 'LoanCreationNotificationAgentId', { value: LoanAutomationAndNotificationAgent.agentId });

    const kb_instruction = 'Use this knowledge base to answer any loan related questions'
    // Bedrock Knowledge Base
    const kb_loan = new bedrock.KnowledgeBase(this, 'BedrockKnowledgeBaseLoan', {
      embeddingsModel: bedrock.BedrockFoundationModel.COHERE_EMBED_ENGLISH_V3,
      instruction: kb_instruction
    });


    new ssm.StringParameter(this, 'KnowledgeBaseIdLoan', {
      parameterName: '/loanassit/KnowledgeBaseIdLoan',
      stringValue: kb_loan.knowledgeBaseId,
    });

    // set the data source of the s3 bucket for the knowledge base
    const loandataSource = new bedrock.S3DataSource(this, 'loandataSource', {
      bucket: loanPolicyDocsBucket,
      knowledgeBase: kb_loan,
      dataSourceName: 'loan-knowledge-base',
      chunkingStrategy: bedrock.ChunkingStrategy.DEFAULT
    });

    LoanAutomationAndNotificationAgent.addKnowledgeBase(kb_loan);
    //Output
    new cdk.CfnOutput(this, 'LoanKnowledgeBaseIdOutput', { value: kb_loan.knowledgeBaseId });

    //User interface constructs and code

    // Retrieve default VPC associated with Cloud9
    const vpc = ec2.Vpc.fromLookup(this, 'DefaultVpc', {
      isDefault: true
    });


    //Define the Lambda function Role
    const apiForInsureAssistAgentRole = new Role(this, 'ApiForInsureAssistAgentRole', {
      roleName: 'ApiForInsureAssistAgentRole',
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    //Define the Lambda function for invoking the Insure Assist Bedrock Agent
    const lambdaFunctionApiCallingInsureAssistAgent = new lambda.Function(this, 'ApiForInsureAssistAgent', {
      runtime: lambda.Runtime.PYTHON_3_10,
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'lambda_for_insureassist_agent')), // Provide the path to your Lambda function code
      handler: 'lambda_function.lambda_handler', // Assuming your handler function is named 'lambda_handler' in a file named 'index.py'
      memorySize: 512, // Memory allocation for the function in MB
      timeout: cdk.Duration.seconds(900), // Maximum execution time for the function in seconds
      role: apiForInsureAssistAgentRole,
      environment: {
//          'INSUREASSIST_AGENTID': InsuranceOrchestratorAgent.agentId,
             'INSUREASSIST_AGENTID': LoanAutomationAndNotificationAgent.agentId
      }
    });

    //Create an ALB for the Insure Assist Lambda which will invoke the  Insure Assist Bedrock Agent
    const albApiCallingInsureAssistAgent = new elbv2.ApplicationLoadBalancer(this, 'InsureAssistApiLoadBalancer', {
      vpc,
      internetFacing: true, // This will create a publicly accessible ALB
    });

    // Create a listener for the ALB
    const insureAssistApiListener = albApiCallingInsureAssistAgent.addListener('insureAssistApiListener', {
      port: 80,
      open: true,
    });

    // Add a default target group for the Lambda function
    const insureAssistApitargetGroup = insureAssistApiListener.addTargets('InsureAssistAPIGroup', {
      targets: [new targets.LambdaTarget(lambdaFunctionApiCallingInsureAssistAgent)]
    });

    // Define CDK output for ALB DNS name
    new cdk.CfnOutput(this, 'InsureAssistApiAlbDnsName', {
      value: albApiCallingInsureAssistAgent.loadBalancerDnsName
    });


    // Create the UI stack ###########################

    // Upload the updated index.html to the S3 bucket
    new s3deploy.BucketDeployment(this, 'DeployIndexHtml', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '..', 'lambdas', 'ui_chatbot'))],
      destinationBucket: uiHtmlBucket,
      destinationKeyPrefix: '', // Set destinationKeyPrefix to empty string for root of bucket
    });



    //Define the Lambda function Role  for the UI Lambda
    const insureAssistUiLambdaRole = new Role(this, 'insureAssistUiLambdaRole', {
      roleName: 'insureAssistUiLambdaRole',
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [ManagedPolicy.fromAwsManagedPolicyName('AdministratorAccess')],
    });

    // Define a Lambda function for the UI
    const lambdaFunctionInsureAssistUI = new lambda.Function(this, 'InsureAssistUILambda', {
      runtime: lambda.Runtime.PYTHON_3_10,
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'lambdas', 'ui_chatbot')), // Provide the path to your Lambda function code
      handler: 'lambda_function.lambda_handler', // Assuming your handler function is named 'lambda_handler' in a file named 'index.py'
      memorySize: 512, // Memory allocation for the function in MB
      timeout: cdk.Duration.seconds(900), // Maximum execution time for the function in seconds
      environment: {
        HTML_BUCKET_NAME: uiHtmlBucket.bucketName,
        IMAGE_BUCKET_SUBMITTED_BY_UI: identityProofImagesBucket.bucketName,
        INSURE_ASSIST_API_ALB_DNS_NAME: albApiCallingInsureAssistAgent.loadBalancerDnsName
      },
      role: insureAssistUiLambdaRole
    });

    // Create an ALB for the Insure Assist UI
    const InsureAssistUIalb = new elbv2.ApplicationLoadBalancer(this, 'InsureAssistUILoadBalancer', {
      vpc,
      internetFacing: true, // This will create a publicly accessible ALB
    });

    // Create a listener for the ALB
    const listener = InsureAssistUIalb.addListener('InsureAssistUIListener', {
      port: 80,
      open: true,
    });

    // Add a default target group for the Lambda function
    const targetGroup = listener.addTargets('InsureAssistUIGroup', {
      targets: [new targets.LambdaTarget(lambdaFunctionInsureAssistUI)]
    });



    // Store the ALB DNS name as a parameter in Parameter Store
    new ssm.StringParameter(this, 'InsureAssistALBDnsNameParameter', {
      parameterName: '/insureassist/ui_alb_dns_name',
      stringValue: InsureAssistUIalb.loadBalancerDnsName,
    });

    // Define CDK output for ALB DNS name
    new cdk.CfnOutput(this, 'InsureAssistUIAlbDnsName', {
      value: InsureAssistUIalb.loadBalancerDnsName
    });

    // Output the bucket name
    new cdk.CfnOutput(this, 'ImageBucketName', {
      value: damageImagesBucket.bucketName,
    });

  }
}