# ADR 0010 — Research strategies and optional RL boundary

- Status: Proposed for GPT Reviewer review
- Date: 2026-09-21

## Decision

Rule based strategies remain behind the existing paper-only `BaseStrategy` and `OrderRequest` risk gates. Funding arbitrage keeps explicit spot/perpetual legs and cannot synthesize missing market inputs. SMC signals are causal and may emit partial-exit metadata, while actual execution remains subject to the broker. Walk-forward utilities are descriptive only. PPO is optional and must fail closed when `stable-baselines3` or a reviewed Gymnasium adapter is unavailable.

## Constraints

No live/testnet trading, no API keys, no private keys, no real-money execution, no bypass of circuit breaker, margin, funding provenance or idempotency invariants. Any performance figure is AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED until an independent review verifies data, manifests and artifacts.
