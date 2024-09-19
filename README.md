## Digital Lending Assitant powered by Amazon Bedrock Agent: DigiDhan


### Deploy the solution
This project is built using the [AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/). 
- For refernce here are the versions of node and aws cdk that have been used.
- Node.js: v20.16.0
- [AWS CDK](https://github.com/aws/aws-cdk/releases/tag/v2.143.0): 2.143.0
- Command to install a specific version of aws-cdk is  
    ```npm install -g aws-cdk@X.YY.Z```

1. Clone this repository.
    ```shell
    git clone https://github.com/aws-samples/DigiDhan-GenAI-FSI-LendingSolution-India.git
    ```

2. Enter the code sample backend directory.
    ```shell
    cd DigiDhan-GenAI-FSI-LendingSolution-India/
    ```

3. Install packages
   ```shell
   npm install
   npm install -g aws-cdk
   ```

4. Boostrap AWS CDK resources on the AWS account. If deployed in any region other tahn us-east the stack may fail due to lambda layers dependecy, you can either comment the layer and deploy in other region or just deploy in us-east-1
    ```shell
    cdk bootstrap aws://ACCOUNT_ID/REGION
    ```

5. Enable Access to Amazon Bedrock Models
> You must explicitly enable access to models before they can be used with the Amazon Bedrock service. Please follow these steps in the [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) to enable access to the models (```Anthropic::Claude (Sonnet)``` and ```Cohere::Embed English```):.

6. Deploy the sample in your account. 
    ```shell
    cdk deploy --all
    ```
The command above will deploy one stack in your account.

To protect you against unintended changes that affect your security posture, the AWS CDK Toolkit prompts you to approve security-related changes before deploying them. You will need to answer yes to get all the stack deployed.

Note: The IAM role creation in this example is for illustration only. Always provision IAM roles with the least required privileges. 
      The Stack deployment roughly takes 10-15 minutes.
      Once the stack is successfully deployed you can find **InsureAssistApiAlbDnsName** in the output section of the stack, this is the application endpoint.

## Post Deployment Actions
1. Go To Bedrock console in the deployed region and edit the Agent. Modify additional settings and enable **user Input** which decides whether the agent can prompt additional information from the user when it does not have enough information to respond to an utterance. 
<img width="1037" alt="image" src="https://github.com/user-attachments/assets/bf50b7fe-7ea7-40cf-b045-52db0fc619d6">

## Architecture
<img width="1037" alt="image" src="https://github.com/user-attachments/assets/7d413d7f-c22c-4eea-a720-f38606b2b975">


## Clean up

Do not forget to delete the stack to avoid unexpected charges.

First make sure to remove all data from the Amazon Simple Storage Service (Amazon S3) Bucket.

```shell
    cdk destroy
```
# Content Security Legal Disclaimer
The sample code; software libraries; command line tools; proofs of concept; templates; or other related technology (including any of the foregoing that are provided by our personnel) is provided to you as AWS Content under the AWS Customer Agreement, or the relevant written agreement between you and AWS (whichever applies). You should not use this AWS Content in your production accounts, or on production or other critical data. You are responsible for testing, securing, and optimizing the AWS Content, such as sample code, as appropriate for production grade use based on your specific quality control practices and standards. Deploying AWS Content may incur AWS charges for creating or using AWS chargeable resources, such as running Amazon EC2 instances or using Amazon S3 storage.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

