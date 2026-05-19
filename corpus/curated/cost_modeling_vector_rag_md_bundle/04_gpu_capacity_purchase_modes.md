# GPU Capacity Purchase Modes

## Overview

GPU economics depend heavily on **purchase mode**, not only provider. The same model can look expensive on on-demand managed inference, cheap on reserved capacity, and extremely cheap on spot — until interruptions or underutilization are included.

## 1. Token-priced API

### Billing shape

```text
cost = tokens × price_per_token
```

### Pros

- No idle capacity cost.
- No GPU orchestration.
- No autoscaling complexity.
- Fast model switching.
- Good for prototypes and variable workloads.

### Cons

- Cost grows linearly forever.
- Less control over batching and kernel optimizations.
- Data governance constraints may apply.
- Provider rate limits and model deprecations matter.

### Best fit

- Low QPS.
- Bursty traffic.
- Early product iteration.
- Small or medium ingestion volume.
- Teams without platform/SRE capacity.

## 2. On-demand GPU VM or managed endpoint

### Billing shape

```text
cost = gpu_hourly_price × provisioned_hours × gpu_count
```

### Pros

- Predictable capacity.
- More control over model, batching, quantization, and deployment stack.
- Can be cheaper at high utilization.
- Easier to meet strict residency or privacy requirements.

### Cons

- You pay while idle.
- Autoscaling and cold starts are hard.
- You own monitoring, patching, rollout, and incident response.
- Requires performance engineering.

### Best fit

- Steady production workloads.
- High daily batch embedding.
- Custom/fine-tuned models.
- Internal high-throughput systems.

## 3. Reserved/committed capacity

### Billing shape

```text
effective_used_hour = reserved_hourly_price / scheduled_utilization
```

A 35% discount can still be bad if the GPU is only used half the time.

### Pros

- Lower nominal hourly price.
- Predictable capacity access.
- Good for steady 24×7 workloads.

### Cons

- Commitment risk.
- Waste if traffic or model plans change.
- Harder to unwind after architecture changes.

### Best fit

- Mature workloads with stable traffic.
- Long-lived model stack.
- Strong utilization history.

## 4. Spot/preemptible GPU

### Billing shape

```text
effective_used_hour = spot_hourly_price / (1 - interruption_loss_fraction)
                      + restart_penalty_per_productive_hour
```

### Pros

- Can be dramatically cheaper.
- Excellent for batch embedding, re-embedding, backfills, and experimentation.

### Cons

- Interruptions.
- Availability uncertainty.
- More orchestration complexity.
- Poor fit for strict low-latency serving unless paired with fallback capacity.

### Best fit

- Offline embedding.
- Backfills.
- Reindexing.
- Evaluation batch jobs.
- Training/fine-tuning jobs with checkpointing.

## 5. Capacity blocks / scheduled capacity

### Billing shape

```text
cost = fixed_block_price for a fixed time window
```

### Pros

- Guaranteed access during booked windows.
- Useful for planned large jobs.
- Can be cheaper than ad hoc on-demand for specific high-end GPUs.

### Cons

- Requires scheduling discipline.
- Idle time inside block is wasted.
- Not flexible for unpredictable traffic.

### Best fit

- Planned re-embedding after model upgrade.
- Large backfills.
- Benchmark/evaluation campaigns.
- Periodic rebuilds.

## 6. Dedicated managed model hosting

Dedicated managed hosting sits between token API and self-hosting.

### Billing shape

```text
cost = instance_hourly_or_monthly_price × instances
```

### Pros

- More predictable than token pricing at high usage.
- Less ops burden than fully self-hosted VMs.
- Often comes with managed scaling/security/monitoring options.

### Cons

- Minimum spend.
- Less low-level control than self-hosting.
- May still require capacity planning.

### Best fit

- Mid-to-high steady usage.
- Teams that need private deployment but not full ops ownership.
- Reranking or embedding workloads with predictable throughput.

## 7. GPU sizing by task

| Task | Usual capacity profile | Notes |
|---|---|---|
| Query embedding | latency-sensitive, small batches | API often wins until high QPS |
| Document embedding | throughput-oriented, large batches | self-host/spot often wins at scale |
| Cross-encoder reranking | expensive per query, candidate-dependent | model size and fanout drive cost |
| LLM generation | token-heavy and latency-sensitive | KV cache, batching, and model size matter |
| ANN search | often CPU/RAM/SSD-bound rather than GPU-bound | depends on algorithm/vendor |
| Index build | bursty, parallelizable | schedule on cheaper capacity when possible |

## 8. Procurement checklist

Before committing to self-hosting or reserved GPUs, collect:

- measured tokens/sec for the actual model;
- measured p50/p95/p99 latency under batching;
- real traffic distribution, not just average QPS;
- target SLO;
- required replicas and failover policy;
- expected model upgrade cadence;
- data residency constraints;
- on-call ownership;
- expected utilization by hour of day;
- interruption tolerance;
- fallback path if capacity is unavailable.

## 9. Rule of thumb

- **API first** for unknown or spiky workloads.
- **Spot/preemptible** for offline embedding and reindexing.
- **On-demand/dedicated** for stable workloads that need control.
- **Reserved/committed** only after measuring utilization.
- **Capacity blocks** for planned large jobs.
