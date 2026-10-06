# Final validation checklist

Run from the repository root:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q edge cloud tests
.venv\Scripts\python.exe scripts\package_cloud_lambda.py --output dist\cloudcrowd-lambda.zip
cd frontend
npm run build
```

When hardware is available:

```powershell
cd ..
.venv\Scripts\python.exe -m edge.main --width 1280 --height 720
```

When AWS credentials, resources, and TLS files are available:

```powershell
.venv\Scripts\python.exe scripts\smoke_test_aws_pipeline.py --timeout 120
```

Do not mark the AWS stages as verified unless the smoke test confirms IoT receipt, Lambda execution, DynamoDB update, and an API response matching the written state.
