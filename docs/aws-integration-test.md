# AWS integration test

This documents the real AWS path used by the project:

`edge/mqtt/publisher.py` → AWS IoT Core → `cloud.lambda.handler.lambda_handler` → DynamoDB → `cloud.api.routes.lambda_handler` → React.

## Required environment variables

Set these in a local `.env` file or the process environment. `.env` and certificate files are ignored and must not be committed.

```dotenv
AWS_REGION=<aws-region>
AWS_IOT_ENDPOINT=<account>-ats.iot.<region>.amazonaws.com
AWS_IOT_CLIENT_ID=<thing-client-id>
AWS_IOT_TOPIC=cloudcrowd/telemetry
AWS_IOT_CA_PATH=<local-path-to-AmazonRootCA1.pem>
AWS_IOT_CERT_PATH=<local-path-to-device-certificate.pem.crt>
AWS_IOT_PRIVATE_KEY_PATH=<local-path-to-private-key.pem.key>
AWS_IOT_PORT=8883
AWS_IOT_KEEPALIVE=60
MQTT_QOS=1
MQTT_RETAIN=false

DYNAMODB_TABLE=cloudcrowd-occupancy
FACILITY_CAPACITY=<facility-capacity>
REPORTING_INTERVAL_SECONDS=60
IOT_PROCESSOR_FUNCTION_NAME=<deployed-processor-lambda-name>
API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/<stage>
```

AWS CLI and boto3 use the normal AWS credential chain. No AWS access keys, certificate contents, or private keys are accepted by the scripts or stored in this repository.

## AWS resources required

The CloudFormation template at `cloud/deployment/template.yaml` configures:

- AWS IoT Core topic rule and Lambda invoke permission
- IoT device policy attachment for the provisioned certificate
- Telemetry processor Lambda
- DynamoDB latest-state table keyed by `location_id`
- API Lambda with `GET /telemetry/latest` and CORS OPTIONS support
- API Gateway deployment and stage

The IoT device certificate and private key must be provisioned separately. The Lambda package is created from the repository's `cloud/` package.

## Exact commands

From the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe scripts\package_cloud_lambda.py --output dist\cloudcrowd-lambda.zip
aws s3 cp dist\cloudcrowd-lambda.zip s3://<artifact-bucket>/cloudcrowd-lambda.zip
aws cloudformation deploy `
  --template-file cloud\deployment\template.yaml `
  --stack-name cloudcrowd-analytics `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
  LambdaCodeBucket=<artifact-bucket> `
  LambdaCodeKey=cloudcrowd-lambda.zip `
  FacilityCapacity=<facility-capacity> `
  ReportingIntervalSeconds=60 `
  DefaultFacilityId=<facility-id> `
  TableName=cloudcrowd-occupancy `
  IotTopic=cloudcrowd/telemetry `
  IotClientId=<thing-client-id> `
  IotCertificateArn=<provisioned-certificate-arn>

aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text
aws cloudformation describe-stacks --stack-name cloudcrowd-analytics --query "Stacks[0].Outputs" --output table
.venv\Scripts\python.exe scripts\smoke_test_aws_pipeline.py --timeout 120
```

The smoke test publishes one unique facility message using the existing publisher, observes it through an MQTT subscription, checks the processor Lambda log, waits for the matching DynamoDB item, and compares `GET /telemetry/latest?facility_id=<unique-id>` with the expected state. The React service uses the same API response contract and endpoint.

## Verification results

The real AWS smoke test was attempted on 2026-10-06 (Asia/Calcutta). It could not start because this workspace has no AWS CLI on PATH, no local AWS CLI installation, no configured AWS credentials, no `.env`, and no AWS IoT certificate/key configuration. Therefore no PASS result is claimed for IoT receipt, Lambda execution, DynamoDB update, API response, or React live receipt.

Local validation completed:

- `tests/test_cloud_pipeline.py` and `tests/test_aws_iot_publisher.py`: 16 passed.
- Lambda package creation is available through `scripts/package_cloud_lambda.py`.

## Known limitations

- Deployment and real AWS verification require an AWS CLI installation, authenticated AWS credential profile, provisioned IoT certificate, and populated environment variables.
- The smoke script verifies the API response consumed by React, but does not drive a browser; React runtime receipt remains to be verified after AWS access is configured.
- The API exposes latest facility state only. Historical chart data is accumulated by frontend polling rather than read from an AWS history endpoint.
