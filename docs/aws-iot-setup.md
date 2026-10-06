# AWS IoT Core MQTT setup

This project is prepared for AWS IoT Core mutual-TLS MQTT configuration. The current edge publisher validates configuration and prepares the Paho TLS client, but it does not connect or publish automatically during setup.

## Required environment variables

Set these variables in a local `.env` file or in the process environment:

```dotenv
AWS_IOT_ENDPOINT=your-endpoint-ats.iot.your-region.amazonaws.com
AWS_IOT_CLIENT_ID=cloudcrowd-edge-01
AWS_IOT_TOPIC=cloudcrowd/telemetry
AWS_IOT_CA_PATH=C:\path\to\AmazonRootCA1.pem
AWS_IOT_CERT_PATH=C:\path\to\device-certificate.pem.crt
AWS_IOT_PRIVATE_KEY_PATH=C:\path\to\private-key.pem.key
```

The following optional settings are also supported by the existing publisher:

```dotenv
AWS_IOT_PORT=8883
AWS_IOT_KEEPALIVE=60
MQTT_QOS=1
MQTT_RETAIN=false
```

`python-dotenv` loads `.env` values when `edge.mqtt.publisher` is imported. Process environment variables take precedence over values in `.env`.

## Certificate requirements

The three file paths must point to readable local files:

- `AWS_IOT_CA_PATH`: Amazon Root CA certificate
- `AWS_IOT_CERT_PATH`: AWS IoT device certificate
- `AWS_IOT_PRIVATE_KEY_PATH`: device private key

The publisher configures Paho MQTT with:

```python
client.tls_set(
    ca_certs=AWS_IOT_CA_PATH,
    certfile=AWS_IOT_CERT_PATH,
    keyfile=AWS_IOT_PRIVATE_KEY_PATH,
)
```

No certificate contents or private-key contents belong in source code or `.env` files.

## Validation behavior

AWS IoT mode is selected when any `AWS_IOT_*` variable is set. The publisher then requires all six variables:

- `AWS_IOT_ENDPOINT`
- `AWS_IOT_CLIENT_ID`
- `AWS_IOT_TOPIC`
- `AWS_IOT_CA_PATH`
- `AWS_IOT_CERT_PATH`
- `AWS_IOT_PRIVATE_KEY_PATH`

It raises a clear `ValueError` when configuration is incomplete and a `FileNotFoundError` when a certificate or key path does not point to a file.

When no AWS IoT variables are set, the existing local MQTT defaults remain active (`localhost:1883` and `cloudcrowd/telemetry`).

## Security and repository rules

- Do not commit `.env` files containing local configuration.
- Do not commit CA certificates, device certificates, private keys, or other TLS artifacts.
- Use AWS IoT policies and deployment secret injection outside this repository.
- Do not place AWS access keys in the edge MQTT configuration.

The repository `.gitignore` excludes `.env` files and common certificate/private-key formats.

## Current status

This is configuration preparation only. The project has not connected to AWS IoT Core or published an AWS MQTT message as part of this change.
