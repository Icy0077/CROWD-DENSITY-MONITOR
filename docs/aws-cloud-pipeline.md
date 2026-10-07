# AWS Cloud Pipeline

This deployment connects the existing edge MQTT publisher to AWS IoT Core, a telemetry Lambda, DynamoDB latest-state storage, and the existing `GET /telemetry/latest` response contract. The CloudFormation stack does not create device certificates or private keys; provision those through the organization's AWS IoT certificate process.

## Required values

Edge publisher settings use the existing environment variables:

```dotenv
AWS_IOT_ENDPOINT=your-account-ats.iot.your-region.amazonaws.com
AWS_IOT_CLIENT_ID=cloudcrowd-edge-01
AWS_IOT_TOPIC=cloudcrowd/telemetry
AWS_IOT_CA_PATH=C:\path\to\AmazonRootCA1.pem
AWS_IOT_CERT_PATH=C:\path\to\device-certificate.pem.crt
AWS_IOT_PRIVATE_KEY_PATH=C:\path\to\private-key.pem.key
AWS_IOT_PORT=8883
AWS_IOT_KEEPALIVE=60
MQTT_QOS=1
```

Never store certificate contents, private keys, or static AWS access keys in the repository. Use the AWS CLI credential chain (for example, an approved IAM Identity Center profile) for deployment and smoke-test AWS SDK calls.

The stack requires `FacilityCapacity`, the facility's configured capacity, and `ReportingIntervalSeconds`, the nominal edge publishing interval. `EdgePipeline` aggregates crossings and publishes the measured duration of each batch as `reporting_interval_seconds`, including the final partial interval when the input stream ends. Lambda maps the message to the existing API/state schema, calculates occupancy percentage and status, and applies Little's Law using arrivals per minute derived from that measured duration. The configured interval is retained as a fallback for older edge messages that omit the duration.

## Package and deploy

From the project root, package the cloud Python modules. The Lambda runtime provides boto3; this package contains only the project's `cloud/` modules. Upload each package to a new content-versioned key rather than replacing the prior deployment artifact. The current pinned artifact is `cloudcrowd-lambda-faa8977df322.zip`; `LambdaCodeKey` defaults to this key for fresh deployments.

```powershell
.venv\Scripts\python.exe scripts\package_cloud_lambda.py --output dist\cloudcrowd-lambda.zip
aws s3 cp dist\cloudcrowd-lambda.zip s3://crowd-density-lambda-2026/cloudcrowd-lambda-faa8977df322.zip
aws cloudformation deploy `
  --template-file cloud\deployment\template.yaml `
  --stack-name crowd-density-monitor `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
    LambdaCodeBucket=crowd-density-lambda-2026 `
    LambdaCodeKey=cloudcrowd-lambda-faa8977df322.zip `
    FacilityCapacity=<facility-capacity> `
    ReportingIntervalSeconds=60 `
    DefaultFacilityId=<facility-id> `
    TableName=cloudcrowd-occupancy `
    IotTopic=cloudcrowd/telemetry `
    IotClientId=cloudcrowd-edge-01 `
    IotCertificateArn=<provisioned-device-certificate-arn>
```

The stack creates the encrypted on-demand DynamoDB table, write-only processor role, read-only API role, telemetry processor Lambda, API Lambda, IoT SQL rule and Lambda permission, a topic-scoped device policy attachment, and API Gateway GET/OPTIONS routes with CORS. The certificate ARN must refer to a provisioned certificate in the same account and region. The MQTT client ID must match `IotClientId`.

Get the data endpoint and the deployed API outputs:

```powershell
aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text
aws cloudformation describe-stacks --stack-name cloudcrowd-analytics --query "Stacks[0].Outputs" --output table
```

Set `AWS_IOT_ENDPOINT` to the returned endpoint. Set `API_BASE_URL` to the `TelemetryApiBaseUrl` stack output (stage base URL, without a route), `DYNAMODB_TABLE` to `TelemetryTableName`, `FACILITY_CAPACITY` to the same configured capacity, `DEFAULT_FACILITY_ID` to the configured facility ID, and `IOT_PROCESSOR_FUNCTION_NAME` to `TelemetryProcessorFunctionName`. For deployment, CloudFormation configures the Lambda environment automatically. The API defaults `/telemetry/latest` to this configured facility when the React client omits the `facility_id` query parameter; no telemetry is synthesized when state is unavailable.

## End-to-end smoke test

The opt-in smoke test publishes exactly one real MQTT telemetry message with a unique facility ID. It waits for AWS IoT's connection and subscription acknowledgments before publishing, then waits for the same message through the MQTT subscription. It checks the processor's CloudWatch log marker, waits for the matching DynamoDB item, then compares the API response with the expected canonical state.

Set the edge TLS values above and these local smoke-test values in `.env` or the process environment:

```dotenv
AWS_REGION=your-region
DYNAMODB_TABLE=cloudcrowd-occupancy
FACILITY_CAPACITY=<facility-capacity>
REPORTING_INTERVAL_SECONDS=60
IOT_PROCESSOR_FUNCTION_NAME=<stack-output>
API_BASE_URL=https://<api-id>.execute-api.<region>.amazonaws.com/prod
```

Then run:

```powershell
.venv\Scripts\python.exe scripts\smoke_test_aws_pipeline.py --timeout 120
```

Success prints `IOT_RECEIVE`, `LAMBDA_EXECUTION`, `DYNAMODB_UPDATE`, and `API_STATE_MATCH` as `PASS`. The operator identity needs permission to read the target DynamoDB item and query the processor log group; the device certificate policy is attached by the stack. The test prints status only, not credentials or certificate material.

## Verification status

The local handlers and injectable DynamoDB adapter are covered by pytest. A real AWS end-to-end result is not claimed until the stack is deployed with a provisioned device certificate, valid local TLS files, AWS CLI credentials, and the smoke test completes successfully.
