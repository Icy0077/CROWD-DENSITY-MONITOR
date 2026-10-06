# Security and Privacy Audit

This audit reviewed the current project for real secrets, secret exposure, privacy risks, and unsafe configuration. The goal was to fix only clear security and privacy issues without changing the project architecture or adding new features.

## Findings

| Issue | File | Severity | Status | Suggested fix |
| --- | --- | --- | --- | --- |
| The project had no committed `.env` file containing real secrets. The repository includes only `.env.example` placeholders, which are safe template values. | `.env.example`; `frontend/.env.example` | Low | Verified safe | Keep using environment variables and keep `.env` and cert/key files ignored. |
| AWS IoT certificate paths and MQTT credentials are configured through environment variables instead of committed files. This is a safe pattern if the actual files are never added to the repo. | `cloud/iot/device.py`; `edge/mqtt/publisher.py` | Medium | Verified safe | Continue reading secrets from environment variables and never commit PEM files or secret values. |
| The repository did not ignore PEM/cert/key artifacts. If a developer adds real AWS IoT certificate files locally, they could be accidentally committed. | `.gitignore` | Medium | Fixed | Add common certificate/key patterns to `.gitignore` so local TLS material stays out of Git. |
| Frame blurring could be mistaken for a privacy guarantee. The edge detector blurs the local frame in place after inference, but this does not guarantee that people are unidentifiable. | `edge/privacy/privacy_drop.py`; `edge/vision/detector.py` | Medium | Boundary verified; anonymization not guaranteed | Keep frames out of telemetry and storage; do not describe blurring as guaranteed anonymization. |
| There was no evidence of frame persistence or storage of raw frames to disk. The project does not save video frames or snapshots as a normal part of the pipeline. | `edge/vision/detector.py`; `edge/privacy/privacy_drop.py` | Medium | Verified safe | Keep frame processing in memory and avoid writing raw frames to disk unless explicitly required in a future secure workflow. |
| Edge telemetry contains aggregate state and counts, not image or identity fields. Location and timestamp data can still be sensitive and this schema alone does not guarantee anonymity. | `docs/telemetry-schema.md`; `edge/mqtt/publisher.py`; `cloud/lambda/handler.py` | Medium | Schema boundary verified | Keep the telemetry contract limited to aggregate counts and avoid adding image or per-person identifiers; assess location and timestamp sensitivity for deployment. |
| Frontend API configuration is defaulted to a local endpoint and does not include credentials or secret-bearing values. It remains a safe local-only default. | `frontend/src/services/api.js`; `frontend/.env.example` | Low | Verified safe | Keep API base URL in environment configuration only and never embed tokens, keys, or credentials into the frontend bundle. |
| Debug logging in the local API server is limited to request path and basic service info. It does not print credentials, tokens, or telemetry payloads with PII. | `cloud/api/local_server.py` | Low | Verified safe | Keep logs minimal and avoid logging raw request bodies, secret material, or unredacted telemetry. |

## Actions taken

- Updated `.gitignore` to ignore certificate and key files such as `.pem`, `.crt`, `.key`, `.p12`, and `.cert`.
- Updated the privacy filter to overwrite the local frame with blurred pixels after inference; this is not a guarantee of anonymization.
- Verified that the edge MQTT path publishes aggregate telemetry fields and does not include frame data.
- Confirmed there are no committed `.env` files with real credentials in the repository.

## Security posture summary

The repository does not currently contain real AWS credentials, access keys, private keys, or certificate material. Certificate/key ignore rules are present. The edge pipeline keeps frames in local processing and publishes aggregate telemetry, but blur should not be treated as an identity-anonymization guarantee.
