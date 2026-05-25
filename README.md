# Janavani

India does not lack grievance portals. It lacks a way to hear thousands of spoken grievances as one civic signal.

Janavani is a voice-first civic issue intelligence layer for India. It turns spoken grievances into structured, clustered, area-wise public issue signals that citizens can join, officials can act on, and engineers can evaluate.

## What it does

- Accepts citizen grievances in Indian languages
- Transcribes and normalizes voice/text input
- Extracts issue, department, urgency, ward, and landmark
- Clusters similar grievances by area and issue
- Lets citizens join/support existing complaint clusters
- Shows repeated civic problems on a public dashboard
- Generates formal complaint drafts for high-volume clusters
- Evaluates the pipeline with `bhasha-test`

## What it is not

It is not another grievance portal. It is an intelligence layer that can sit above existing systems such as CPGRAMS, Jansunwai, Swachhata, or municipal complaint portals.

## Platform strategy

- Android-first Expo React Native citizen app
- iOS support in future via Expo/EAS (same codebase)
- Next.js web dashboard for admins and public issue intelligence
- FastAPI backend

## Quick start

```bash
git clone git@github.com:bobross-ui/janavani.git
cd janavani
make demo        # starts everything, seeds demo data
# open http://localhost:3000 — 4 issue clusters across Wards 2/4/8/11
```
