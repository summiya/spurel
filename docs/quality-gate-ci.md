# CI quality gates

Spurel can turn a persisted benchmark comparison into a CI process result through the
`spurel-quality-gate` command.

The command calls the deployed Spurel quality-gate API. It does not connect directly to
PostgreSQL and does not duplicate the quality-gate metric logic.

## Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | The quality gate passed. |
| `1` | At least one configured regression threshold failed. |
| `2` | The gate was not safely evaluable. |
| `3` | CLI configuration, network, API, or response error. |

CI systems should normally treat every non-zero exit code as a failed job.

`not_evaluable` is deliberately non-zero. A changed benchmark case set or unavailable
required metric should not silently allow a deployment.

## Install

From the repository root:

```bash
python -m pip install -e ./backend
```

This installs:

```text
spurel-quality-gate
```

## Example

The first run is the baseline and the second run is the candidate.

```bash
spurel-quality-gate \
  --api-base-url "https://spurel.example.com" \
  --knowledge-base-id "00000000-0000-0000-0000-000000000001" \
  --dataset-id "00000000-0000-0000-0000-000000000002" \
  --first-run-id "00000000-0000-0000-0000-000000000003" \
  --second-run-id "00000000-0000-0000-0000-000000000004" \
  --max-mrr-drop 0.02 \
  --max-mean-ndcg-drop 0.02 \
  --max-mean-recall-drop 0.03 \
  --max-mean-duration-increase-ms 50
```

At least one threshold must be supplied.

For machine-readable logs:

```bash
spurel-quality-gate ... --json
```

## Optional bearer token

If the deployed Spurel API is protected by bearer authentication, set:

```bash
export SPUREL_API_TOKEN="..."
```

The CLI reads the token from the environment and sends it as an Authorization header.
The token is never accepted as a command-line argument, which avoids placing it directly
in the process argument list.

## GitHub Actions

The repository includes:

```text
.github/workflows/rag-quality-gate.yml
```

It supports both:

- manual `workflow_dispatch`
- reusable `workflow_call`

The workflow succeeds only when the Spurel quality gate returns `pass`.

A regression, `not_evaluable` result, API failure, or CLI configuration error makes the
quality-gate step fail.

### Reusable workflow example

A caller can use the workflow after benchmark runs have already been created:

```yaml
jobs:
  rag-quality:
    uses: ./.github/workflows/rag-quality-gate.yml
    with:
      api_base_url: ${{ vars.SPUREL_API_BASE_URL }}
      knowledge_base_id: ${{ vars.SPUREL_KNOWLEDGE_BASE_ID }}
      dataset_id: ${{ vars.SPUREL_EVALUATION_DATASET_ID }}
      first_run_id: ${{ needs.baseline.outputs.run_id }}
      second_run_id: ${{ needs.candidate.outputs.run_id }}
      max_mrr_drop: "0.02"
      max_mean_ndcg_drop: "0.02"
      max_mean_recall_drop: "0.03"
      max_mean_duration_increase_ms: "50"
    secrets:
      SPUREL_API_TOKEN: ${{ secrets.SPUREL_API_TOKEN }}
```

The workflow does not define what an acceptable regression is. Threshold policy remains
explicit in the caller.

## Supported thresholds

Quality metrics are higher-is-better and use an allowed drop:

```text
--max-mean-precision-drop
--max-mean-recall-drop
--max-mrr-drop
--max-mean-ndcg-drop
--max-mean-judgment-coverage-drop
```

Latency is lower-is-better and uses an allowed increase:

```text
--max-mean-duration-increase-ms
```

Metric-drop values must be between `0` and `1`. Duration increases are milliseconds
and must be non-negative.

## Failure behavior

The CLI fails closed:

- unsupported API response status → exit `3`
- invalid JSON response → exit `3`
- HTTP or network failure → exit `3`
- same baseline/candidate run ID → exit `3`
- no thresholds supplied → exit `3`
- structurally non-comparable runs → exit `2`

This keeps CI behavior explicit instead of allowing ambiguous benchmark results to pass.


## One-command benchmark + gate

When a promoted baseline exists for the candidate's exact retrieval configuration, CI
does not need to supply a baseline run UUID or create the candidate run separately.

Install the backend and run:

```bash
spurel-benchmark-gate \
  --api-base-url "https://spurel.example.com" \
  --knowledge-base-id "00000000-0000-0000-0000-000000000001" \
  --dataset-id "00000000-0000-0000-0000-000000000002" \
  --mode hybrid \
  --top-k 10 \
  --candidate-k 50 \
  --rrf-k 60 \
  --max-mrr-drop 0.02 \
  --max-mean-ndcg-drop 0.02 \
  --max-mean-recall-drop 0.03 \
  --max-mean-duration-increase-ms 50
```

The command performs:

```text
evaluation dataset
        ↓
run candidate dataset evaluation
        ↓
persist candidate run
        ↓
read candidate's actual persisted retrieval config
        ↓
resolve explicitly promoted baseline for that exact config
        ↓
evaluate baseline vs candidate quality gate
        ↓
return CI exit code
```

The candidate run is persisted before baseline resolution and before the gate is
evaluated. If no promoted baseline exists, or if the gate fails, the candidate run
remains available in benchmark history for investigation.

The baseline lookup uses the configuration returned by the persisted candidate run,
including the server-selected embedding provider, model, and dimensions. CI therefore
does not guess the embedding space.

To bypass promoted-baseline resolution for a deliberate cross-configuration comparison,
supply an explicit override:

```bash
spurel-benchmark-gate ... \
  --baseline-run-id "00000000-0000-0000-0000-000000000003"
```

When `--baseline-run-id` is supplied, the baseline-resolution API is skipped.

The exit codes are identical to `spurel-quality-gate`:

```text
0 = pass
1 = regression threshold failed
2 = not evaluable
3 = configuration / API / network / response error
```

### Retrieval modes

`--mode` is required and must be one of:

```text
vector
keyword
hybrid
```

All modes support:

```text
--top-k
```

Hybrid additionally supports:

```text
--candidate-k
--rrf-k
```

When omitted for hybrid mode:

```text
candidate_k = 50
rrf_k = 60
```

Hybrid candidate size must be greater than or equal to `top_k`.

### Machine-readable result

Use:

```bash
spurel-benchmark-gate ... --json
```

The output includes the new candidate run ID and the complete quality-gate response:

```json
{
  "baseline_run_id": "...",
  "baseline_source": "promoted",
  "candidate_run_id": "...",
  "quality_gate": {
    "status": "pass"
  }
}
```

This preserves both baseline selection and candidate run identity when the gate exits
non-zero.

## One-command GitHub Actions workflow

The repository also includes:

```text
.github/workflows/rag-benchmark-gate.yml
```

It supports both manual execution and reusable `workflow_call`.

Example reusable caller:

```yaml
jobs:
  rag-benchmark:
    uses: ./.github/workflows/rag-benchmark-gate.yml
    with:
      api_base_url: ${{ vars.SPUREL_API_BASE_URL }}
      knowledge_base_id: ${{ vars.SPUREL_KNOWLEDGE_BASE_ID }}
      dataset_id: ${{ vars.SPUREL_EVALUATION_DATASET_ID }}
      mode: "hybrid"
      top_k: "10"
      candidate_k: "50"
      rrf_k: "60"
      max_mrr_drop: "0.02"
      max_mean_ndcg_drop: "0.02"
      max_mean_recall_drop: "0.03"
      max_mean_duration_increase_ms: "50"
    secrets:
      SPUREL_API_TOKEN: ${{ secrets.SPUREL_API_TOKEN }}
```

The workflow succeeds only when the newly created candidate benchmark passes every
configured quality threshold.

The reusable workflow's `baseline_run_id` input is optional. When omitted, Spurel
resolves the explicitly promoted baseline for the candidate's exact persisted retrieval
configuration. Set `baseline_run_id` only when an explicit override is intentional.

If no promoted baseline exists for the candidate configuration, the command exits with
code `3` and the newly persisted candidate run ID is still printed for investigation.
