# API vs Self-Host GPU Crossover

## Why the crossover matters

The API-vs-self-host decision is often discussed as though it were about ideology: “managed APIs are expensive” versus “self-hosting is operationally hard.” The correct framing is simpler:

> APIs are usage-metered. GPUs are capacity-metered. The winner depends on sustained utilization, workload shape, and operational overhead.

For low or bursty workloads, a token-priced API is usually cheaper because you only pay for work done. For high-throughput steady workloads, self-hosted or dedicated GPUs can be cheaper because a fixed hourly cost is amortized over many requests.

## Baseline assumptions used in the worked examples

These are modeling assumptions, not benchmark guarantees:

| Variable | Value |
|---|---:|
| Month length | 30 days |
| Hours/month | 720 |
| Seconds/month | 2,592,000 |
| Query embedding tokens | 32 tokens/query |
| Hosted embedding price example | $0.08 / 1M tokens |
| A10G-class hourly example | $1.52/hour |
| A100-class hourly example | $2.00/hour |
| H100-class hourly example | $4.326/hour |

The low-cost embedding price reflects the report’s provider-pricing snapshot. GPU examples are representative price points from official or provider-linked pricing sources, but exact prices vary by region and purchase mechanism.

## Core break-even formula

```text
q* = (gpu_hourly_price × hours_per_month) /
     (seconds_per_month × avg_query_tokens × api_price_per_million_tokens / 1,000,000)
```

Where:

- `q*` is the break-even sustained QPS for one GPU.
- `gpu_hourly_price × hours_per_month` is the monthly fixed GPU cost.
- `seconds_per_month × avg_query_tokens × api_price_per_million_tokens / 1,000,000` is the hosted API cost per 1 QPS sustained for the month.

## Worked example: query embeddings only

At **$0.08 per million tokens** and **32 tokens/query**:

```text
API monthly cost per 1 sustained QPS
= 2,592,000 queries/month × 32 tokens × $0.08 / 1,000,000
= $6.63552 per sustained QPS per month
```

Now compare against fixed GPU monthly cost:

| GPU price | Monthly GPU cost | Break-even QPS |
|---:|---:|---:|
| $1.52/hour | $1,094.40? wait: 1.52×720 = $1,094.40 | ~165 QPS |
| $2.00/hour | $1,440.00 | ~217 QPS |
| $4.326/hour | $3,114.72 | ~469 QPS |

The earlier report snapshot rounded some examples differently depending on source-specific monthly assumptions. Use the formula above for exact modeling.

## Why break-even can shift dramatically

### 1. Query length

If query length doubles from 32 to 64 tokens, hosted API cost doubles, and self-host crossover QPS roughly halves.

| Avg query tokens | API cost per sustained QPS/month at $0.08/M | A10G-class crossover at $1.52/hr |
|---:|---:|---:|
| 16 | $3.32 | ~330 QPS |
| 32 | $6.64 | ~165 QPS |
| 64 | $13.27 | ~82 QPS |
| 128 | $26.54 | ~41 QPS |

### 2. API price

If the embedding API price rises from $0.08/M to $0.16/M, the crossover QPS halves.

| API price / 1M tokens | A10G-class crossover, 32-token query |
|---:|---:|
| $0.02 | ~660 QPS |
| $0.08 | ~165 QPS |
| $0.16 | ~82 QPS |
| $1.00 | ~13 QPS |

This is why the same self-host decision can be “obviously wrong” for a very cheap embedding API but “obviously right” for a more expensive embedding or reranker.

### 3. Labor and platform overhead

Suppose self-hosting adds **0.1 fully loaded FTE** at **$220k/year**:

```text
monthly_labor = 220,000 × 0.1 / 12 = $1,833/month
```

A10G-class self-host monthly cost becomes:

```text
$1,094 + $1,833 = $2,927/month
```

Break-even becomes:

```text
$2,927 / $6.63552 ≈ 441 QPS
```

At **0.25 FTE**, monthly labor is about **$4,583**, and the break-even is roughly:

```text
($1,094 + $4,583) / $6.63552 ≈ 856 QPS
```

This is why “GPU cheaper than API” is incomplete. Labor can erase the savings until the workload is quite large.

### 4. High availability and spare capacity

If production requires active-active replicas or N+1 failover, the GPU cost is no longer one GPU:

```text
C_self_HA = (active_gpus + standby_gpus) × gpu_hourly_price × hours_per_month
```

For example, two active GPUs plus one standby triples the baseline capacity cost.

### 5. Utilization

GPU utilization must be **productive utilization**, not dashboard utilization. Productive utilization excludes:

- warmup time;
- queue-empty periods;
- restart/redeploy windows;
- batch padding inefficiency;
- token length skew;
- canary capacity;
- failover reserve;
- monitoring/sidecar overhead;
- model download and cold starts.

A GPU at 70% technical utilization may only deliver 40–50% productive business utilization if traffic is bursty.

## Offline batch embedding is different

Offline embedding usually favors self-hosting earlier because it is easier to keep GPUs full. For example:

```text
API document embedding cost = docs/day × 30 × avg_doc_tokens × price_per_million / 1,000,000
```

At 300 tokens/document and $0.08/M tokens:

| Docs/day | Monthly tokens | API cost/month |
|---:|---:|---:|
| 100,000 | 900M | $72 |
| 1,000,000 | 9B | $720 |
| 3,000,000 | 27B | $2,160 |
| 10,000,000 | 90B | $7,200 |

If one A10G-class GPU costs about $1,094/month and can be kept highly utilized, the pure compute break-even for batch embedding is around the low millions of docs/day under these assumptions.

## Decision rule

Use managed/API embeddings when:

- workload is low or bursty;
- QPS is unknown;
- model choice is still changing;
- team lacks SRE/ML platform capacity;
- compliance does not force self-hosting;
- cost of downtime or infra mistakes exceeds API premium.

Use self-host/dedicated capacity when:

- traffic is steady and high;
- daily batch embedding is large;
- utilization can be measured and kept high;
- model stack is stable;
- custom/fine-tuned embedding or rerank models matter;
- data residency or governance makes API use difficult;
- ops team can own deployment, observability, scaling, and incident response.
