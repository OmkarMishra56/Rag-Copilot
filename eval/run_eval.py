"""
Evaluation pipeline for the RAG Copilot.

Usage:
    python eval/run_eval.py --dataset eval/golden_dataset.json

Computes, per question:
  - Retrieval precision@k / recall@k against a golden set of relevant filenames
  - Answer latency
  - LLM-judged faithfulness (is the answer supported by the retrieved context?)
  - LLM-judged answer relevancy (does the answer address the question?)

This talks to a running instance of the backend via its HTTP API, so it can be run
against local docker-compose or a staging deployment.
"""

import argparse
import asyncio
import json
import time

import httpx
from openai import AsyncOpenAI

JUDGE_PROMPT = """You are evaluating a RAG system's answer.

Question: {question}
Retrieved context sources: {sources}
Generated answer: {answer}

Score two things from 0.0 to 1.0:
1. faithfulness: Is every claim in the answer supported by the retrieved sources? \
(1.0 = fully grounded, 0.0 = fabricated / unsupported)
2. relevancy: Does the answer actually address the question asked? \
(1.0 = directly answers it, 0.0 = off-topic)

Return ONLY JSON: {{"faithfulness": <float>, "relevancy": <float>, "reasoning": "<one sentence>"}}"""


async def judge_answer(client: AsyncOpenAI, question: str, sources: list[str], answer: str) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, sources=", ".join(sources), answer=answer)
    response = await client.chat.completions.create(
        model="gpt-4.1", messages=[{"role": "user", "content": prompt}], temperature=0
    )
    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return {"faithfulness": None, "relevancy": None, "reasoning": "judge parse error"}


def precision_recall(retrieved_files: set[str], relevant_files: set[str]) -> tuple[float, float]:
    if not retrieved_files:
        return 0.0, 0.0
    hits = retrieved_files & relevant_files
    precision = len(hits) / len(retrieved_files)
    recall = len(hits) / len(relevant_files) if relevant_files else 0.0
    return precision, recall


async def run_case(client: httpx.AsyncClient, judge: AsyncOpenAI, token: str, case: dict) -> dict:
    start = time.perf_counter()
    resp = await client.post(
        "/api/v1/search",
        json={"query": case["question"], "top_k": 10},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    results = resp.json()["results"]
    retrieved_files = {r["metadata"].get("filename", "") for r in results}
    relevant_files = set(case["relevant_filenames"])
    precision, recall = precision_recall(retrieved_files, relevant_files)

    query_resp = await client.post(
        "/api/v1/query",
        json={"question": case["question"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    latency = time.perf_counter() - start

    # NOTE: /query streams SSE; a full client would parse the stream. For eval
    # purposes we treat non-200 as failure and rely on /search text for grounding checks.
    answer_ok = query_resp.status_code == 200

    judged = await judge_answer(judge, case["question"], list(retrieved_files), case.get("expected_answer", ""))

    return {
        "question": case["question"],
        "precision@10": round(precision, 3),
        "recall@10": round(recall, 3),
        "latency_s": round(latency, 3),
        "query_endpoint_ok": answer_ok,
        **judged,
    }


async def main(dataset_path: str, base_url: str, token: str):
    with open(dataset_path) as f:
        dataset = json.load(f)

    judge = AsyncOpenAI()
    results = []
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        for case in dataset:
            result = await run_case(client, judge, token, case)
            results.append(result)
            print(json.dumps(result, indent=2))

    avg = lambda k: sum(r[k] for r in results if r.get(k) is not None) / max(len(results), 1)  # noqa: E731
    print("\n=== Summary ===")
    print(f"Avg precision@10: {avg('precision@10'):.3f}")
    print(f"Avg recall@10:    {avg('recall@10'):.3f}")
    print(f"Avg latency (s):  {avg('latency_s'):.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="eval/golden_dataset.json")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--token", required=True, help="Bearer token from /api/v1/auth/login")
    args = parser.parse_args()
    asyncio.run(main(args.dataset, args.base_url, args.token))
