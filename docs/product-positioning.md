# Janavani — Product Positioning

## One sentence

India does not lack grievance portals. It lacks a way to hear thousands of spoken grievances as one civic signal.

## What Janavani does

Janavani is a voice-first civic issue intelligence layer for India. Citizens speak or type complaints in their own language — Hindi, Marathi, Tamil, Hinglish — and Janavani extracts structured civic signal: what the issue is, which department should handle it, how urgent, where, and whether it matches other complaints nearby.

The output is not an individual ticket. It is a **cluster** — a public, joinable, area-wise signal that shows repeated civic problems before they become crises.

## How it's different from a grievance portal

| Grievance portals (CPGRAMS, municipal apps) | Janavani |
|---|---|
| One complaint → one ticket → one resolution | Many complaints → one cluster → one civic signal |
| Requires citizen to know department/category | Extracts department and category automatically |
| Text-only, form-driven | Voice-first — speak naturally |
| No language support for regional scripts | Hindi, Marathi, Tamil, Hinglish, English — and growing |
| No clustering of similar complaints | Automatic cluster matching by category + ward + token similarity (semantic embeddings planned in 1.3) |
| No public visibility into repeated issues | Public dashboard showing area-wise issue density |
| Individual resolution tracking | Collective urgency scoring and formal complaint drafting |

Janavani is not another portal. It is an intelligence layer that can sit above existing systems.

## Core technical choices

- **Android-first Expo React Native** citizen app with voice capture and location
- **FastAPI backend** with a provider abstraction that swaps between local keyword extraction and Sarvam (India's sovereign AI stack)
- **Next.js web dashboard** for public issue intelligence and admin workflows
- **Evaluation-first engineering**: 50-case multilingual `bhasha-test` harness with extraction, redaction, WER, and latency scoring
- **Pre-vector clustering**: English-pivot token overlap (Jaccard), ready for pgvector semantic clustering (planned 1.3)

## AI strategy

Janavani uses a **provider abstraction** so the same pipeline works with zero external dependencies (`AI_PROVIDER=local`) or with Sarvam (`AI_PROVIDER=sarvam`):

- **Local mode**: keyword-based extraction, no-op translation, demo-ready in 60s from clone
- **Sarvam mode**: Saarika for STT, Saaras for STT-translate, Mayura for translation, Bulbul for TTS, Sarvam-M for extraction and draft generation
- **Fallback**: if Sarvam fails, the local provider takes over automatically with circuit breaker protection

## What this is not (yet)

- Not a production-deployed service — a portfolio project demonstrating engineering depth
- Not a replacement for CPGRAMS or municipal portals — an intelligence layer, not a submission system
- Not a multi-tenant SaaS — single demo instance with mock auth
- Not real-time — batch extraction at submission time

## Audience

This project is built for:

- **Engineers evaluating technical depth**: provider abstraction, eval-first design, multilingual NLP pipeline
- **Product reviewers**: voice-first civic tech, Indian language support, data-driven governance
- **Hiring managers**: full-stack (React Native + FastAPI + Next.js), evaluation engineering, AI integration
