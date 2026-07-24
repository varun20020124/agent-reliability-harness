# Rails

An LLM evaluation framework for catching quality regressions between model versions with statistical confidence rather than eyeballing outputs.

**Status:** Active development.

## Features

- Multi-suite evaluation across RAG faithfulness, summarization, and instruction following
- Deterministic scorers (exact match, ROUGE, citation overlap) alongside an LLM-as-judge rubric
- Judge validation against a human-labeled gold set, so you know whether the judge can be trusted
- Bootstrapped confidence intervals on every metric to separate real regressions from sampling noise
- Run history persisted to Postgres for version-over-version comparison

## Architecture

Test suites are defined in YAML — each case carries a prompt, optional context, and an expected answer. An async runner dispatches cases to one or more models through a thin provider adapter layer.

Responses go through two scoring paths. Deterministic scorers handle anything checkable in code. The LLM-as-judge scorer applies a rubric for qualities that aren't, like faithfulness to source context.

Scores land in a stats layer that computes bootstrapped confidence intervals and runs paired comparisons between runs — paired rather than independent, since both models see identical cases and pairing removes case-difficulty variance.

Everything persists to PostgreSQL: per-case scores, run metadata, and model versions. A FastAPI layer exposes endpoints for triggering runs, comparing two runs, and pulling reports.

## Installation

```bash
git clone https://github.com/<you>/evalharness.git
cd evalharness

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # add your API keys
docker compose up -d db   # PostgreSQL

alembic upgrade head
```

## Usage

Run a suite against one or more models:

```bash
python -m evalharness run \
  --suite suites/rag_faithfulness.yaml \
  --models gpt-4o-mini,claude-haiku \
  --output runs/
```

Compare two runs for regressions:

```bash
python -m evalharness compare --baseline runs/v1 --candidate runs/v2
```

Validate the judge against human labels:

```bash
python -m evalharness validate-judge --labels data/gold_labels.jsonl
```

Serve the API:

```bash
uvicorn evalharness.api:app --reload
```

Defining a suite:

```yaml
name: rag_faithfulness
scorers: [citation_overlap, judge_faithfulness]
cases:
  - id: fq_001
    context: "The Apollo 11 mission launched on July 16, 1969..."
    prompt: "When did Apollo 11 launch?"
    expected: "July 16, 1969"
```
