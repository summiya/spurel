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
