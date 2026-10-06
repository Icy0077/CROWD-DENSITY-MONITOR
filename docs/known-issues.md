# Known issues and deferred validation

- Live AWS IoT → Lambda → DynamoDB → API verification requires external AWS credentials, deployed resources, and provisioned certificate files.
- The current API exposes latest state only; the frontend trend is explicitly current-session polling data, not database history.
- Multi-person accuracy, prolonged occlusion, and tracker ID stability need further real-world validation across varied camera angles and lighting.
- The edge process does not restore occupancy from DynamoDB after restart; occupancy is process-local unless a future state-reconciliation feature is added deliberately.
- The frontend package has no dedicated test script; its current automated check is the Vite production build.
- The unused legacy `cloud/iot/device.py` uses a separate certificate variable naming convention from the active `edge/mqtt/publisher.py`; the active edge publisher is the supported path.
