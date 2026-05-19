# Storage, Dimension, Replication, and Index Footprint

## Why storage modeling matters

Storage is not always the largest bill, but it strongly affects:

- memory requirements;
- index algorithm feasibility;
- replica cost;
- backup cost;
- rebuild time;
- network transfer;
- cold-start time;
- cache size;
- tenant isolation strategy.

## Raw vector size

For dense FP32 vectors:

```text
raw_bytes = num_vectors × dimensions × 4
```

For FP16:

```text
raw_bytes = num_vectors × dimensions × 2
```

For int8/SQ:

```text
raw_bytes = num_vectors × dimensions × 1
```

## Raw FP32 examples

| Vectors | 384 dims | 768 dims | 1536 dims | 3072 dims |
|---:|---:|---:|---:|---:|
| 1M | 1.43 GiB | 2.86 GiB | 5.72 GiB | 11.44 GiB |
| 10M | 14.31 GiB | 28.61 GiB | 57.22 GiB | 114.44 GiB |
| 100M | 143.05 GiB | 286.10 GiB | 572.20 GiB | 1.12 TiB |
| 1B | 1.40 TiB | 2.79 TiB | 5.59 TiB | 11.18 TiB |

These are raw lower bounds. They exclude metadata, index overhead, allocator overhead, replicas, and backups.

## HNSW overhead

HNSW stores vectors plus graph links. A rough lower-bound graph estimate is:

```text
graph_bytes ≈ num_vectors × M × bytes_per_neighbor_id × level_multiplier
```

Where:

- `M` is the max number of neighbors per node/layer;
- `bytes_per_neighbor_id` is often 4 or 8;
- `level_multiplier` accounts for upper layers and implementation details.

Example for 100M vectors, M=32, 4-byte neighbor IDs, level multiplier 1.1:

```text
graph_bytes ≈ 100,000,000 × 32 × 4 × 1.1
            ≈ 14.08 GB
```

In real systems, overhead can be higher due to memory allocation, payload indexes, deleted-node handling, and replicas.

## Metadata and payload cost

Metadata can dominate for small vectors or rich documents.

```text
metadata_bytes = num_vectors × avg_metadata_bytes_per_vector
```

Example:

| Vectors | 256 B metadata | 1 KiB metadata | 4 KiB metadata |
|---:|---:|---:|---:|
| 10M | 2.38 GiB | 9.54 GiB | 38.15 GiB |
| 100M | 23.84 GiB | 95.37 GiB | 381.47 GiB |
| 1B | 238.42 GiB | 953.67 GiB | 3.73 TiB |

Permission-aware RAG often stores tenant IDs, document IDs, ACL references, timestamps, source versions, chunk offsets, hashes, and citation fields. These should be counted.

## Replication factor

```text
total_serving_footprint = base_index_footprint × replica_count
```

If the unreplicated index is 800 GB:

| Replica count | Serving footprint |
|---:|---:|
| 1 | 800 GB |
| 2 | 1.6 TB |
| 3 | 2.4 TB |

Add backups separately.

## Backup and snapshot footprint

```text
backup_footprint = full_snapshots × index_size + incremental_snapshots × changed_bytes
```

For regulated systems, restore tests also cost compute and time. Model:

```text
monthly_restore_test_cost = restored_GB × restore_price_per_GB + temporary_compute_hours × compute_hourly
```

## Dual-index storage during migrations

During model upgrades or blue/green reindexing:

```text
temporary_storage = old_index + new_index + validation_artifacts + rollback_snapshots
```

If old and new indexes use the same dimensions, expect close to 2× storage during migration. If the new embedding dimension is larger, temporary storage can exceed 2×.

Example:

```text
old: 100M vectors × 768 × FP32 = 286 GiB raw
new: 100M vectors × 1536 × FP32 = 572 GiB raw
temporary raw = 858 GiB before overhead
```

## Quantization and compression

### Scalar quantization

- FP32 → int8 can reduce vector bytes by ~4×.
- Recall may drop depending on model/data.
- Often useful when memory cost dominates.

### Product quantization

- Encodes vectors as compact codes.
- Can reduce memory/storage dramatically.
- Usually requires reranking/reconstruction or asymmetric distance computation.
- Build and tuning complexity increase.

### Binary/product compression caveat

Compression saves storage and memory but may increase:

- build complexity;
- recall tuning work;
- candidate count needed for same recall;
- reranking cost if more candidates are needed.

Compression is economically positive only if:

```text
storage/memory savings > added search/rerank/build/evaluation cost
```

## Egress and returned payload

Returned payload cost depends on:

```text
GB_returned = queries × results_per_query × avg_payload_bytes / 1e9
```

Example:

```text
10M queries/month × 20 results × 2KB payload ≈ 400GB returned/month
```

If returning full chunks instead of IDs, payload cost and latency rise quickly.

## Storage optimization levers

| Lever | Saves | Risk |
|---|---|---|
| Lower embedding dimension | storage, memory, bandwidth | recall/quality loss |
| Use FP16/int8/SQ | storage/memory | recall loss or implementation constraints |
| Product quantization | large memory savings | tuning and recall tradeoff |
| Store chunks externally | vector DB storage/network | extra fetch latency |
| Store IDs not full text in vector DB | payload cost | requires document store join |
| Deduplicate chunks | embedding/storage/search | dedup errors |
| Separate hot/cold indexes | serving memory | routing complexity |
| TTL stale chunks | storage/write efficiency | freshness correctness risk |
| Compact tombstones | search/storage efficiency | background compute |

## Practical recommendation

For every design, compute four footprints:

```text
1. raw vector footprint
2. serving index footprint
3. replicated serving footprint
4. migration/blue-green peak footprint
```

The fourth number is often the one that breaks budgets during model upgrades.
