# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are facility operators, staff, and managers who need to understand crowd density, movement, and queue pressure in real time from a simple dashboard. They need fast operational awareness without needing to inspect raw camera feeds or rely on a cloud video pipeline.

## Product Purpose

CloudCrowd Analytics turns camera input into crowd intelligence at the edge while keeping raw video local. The product helps operators monitor occupancy, movement trends, and queue conditions so they can respond quickly to congestion, staffing needs, or unusual flow.

Success means operators can understand whether a monitored area is calm, crowded, or congested at a glance, using derived telemetry rather than direct video sharing.

## Positioning

This product is an edge-first, privacy-aware crowd density monitor that publishes only derived telemetry to the cloud. It is differentiated by combining local vision processing, privacy-preserving edge execution, and a lightweight operational dashboard without sending raw frames upstream.

## Operating Context

The system runs on an edge machine that receives camera input from locally connected or networked sources. Detection, tracking, line-crossing logic, and occupancy/queue derivations happen near the source, while the cloud receives only telemetry summaries. The dashboard is a React + Vite interface that polls latest telemetry for a facility and shows the current operational state.

This is meant for monitoring facilities and similar public or semi-public spaces where people flow needs to be tracked for safety, service, and operational efficiency.

## Capabilities and Constraints

- Person detection and tracking run on the edge with YOLOv8n and ByteTrack.
- IN / OUT counting is based on line-crossing logic applied to tracked persons.
- Occupancy and movement data are computed from derived telemetry and exposed through the dashboard.
- The cloud path sends telemetry only; raw video stays at the edge process.
- The dashboard polls the latest state at a regular interval and presents current occupancy, movement, and status.
- The repository contains the edge logic, cloud telemetry flow, and frontend dashboard; AWS resources are configured outside the repo and are not fully represented here.
- The project is currently designed for web-based monitoring and dashboard viewing.

## Brand Commitments

The repository’s product identity is described as privacy-aware, edge-first, and operationally focused. The UI and project language emphasize clarity, calm operational feedback, and actionable crowd intelligence, without exposing raw video or unnecessary detail.

## Evidence on Hand

- README.md: product framing, architecture, feature status, and implementation boundaries
- frontend/: React dashboard and polling behavior
- edge/: detection, tracking, crossing logic, and local processing
- cloud/: Lambda and telemetry processing path
- docs/: design and audit context that provides implementation constraints and status notes

## Product Principles

1. Keep video local and telemetry derived.
2. Make critical operational signals understandable at a glance.
3. Prefer lightweight, edge-first monitoring over cloud-heavy processing.
4. Preserve the integrity of operational metrics while reducing unnecessary UI noise.
5. Keep the system useful to operators who need quick decisions in real time.

## Accessibility & Inclusion

The product should remain readable and understandable at a glance for operational users in fast-moving environments. Visual hierarchy and dashboard clarity are important so operators can distinguish useful live signals from secondary information without requiring deep training or extensive interpretation.
