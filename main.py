import argparse
import asyncio
import aiohttp
import uuid
import time
import json
import csv
import subprocess
from datetime import datetime
import os

os.makedirs("data", exist_ok=True)

PROMPT = "ADD가 무인기 체계를 연구한 적 있나요?"
DEFAULT_SESSION_COUNT = 1  # 동시 실행 세션 수

# 측정할 항목: session_id, start_time, end_time, latency, prompt_tokens, completion_tokens, total_tokens, tps, error
fields = [
    "session_id",
    "start_time",
    "end_time",
    "latency_s",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "tps",
    "error",
    "gpu_util_percent",
    "gpu_memory_mib",
    "output_head",
]


def get_gpu_stats():
    """
    GPU 사용률과 메모리 사용량을 nvidia-smi로 측정합니다.
    """
    try:
        result = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ]
        )
        line = result.decode("utf-8").strip().split("\n")[0]  # 사용중인 GPU 번호: 0~3
        gpu_util, mem_used = line.split(", ")
        return int(gpu_util), int(mem_used)
    except Exception as e:
        return -1, -1  # 실패 시


async def test_single_session(session_id: str, url: str, semaphore, results, session_count):
    async with semaphore:
        messages = [
            {
                "role": "system",
                "content": "/no_think 당신은 ADD의 공식 AI 비서입니다. 시스템 테스트 중입니다.",
            },
            {
                "role": "user",
                "content": PROMPT,
            },
        ]

        payload = {
            "messages": messages,
            "stream": True,
            "temperature": 0,
            "top_p": 0.8,
            "max_tokens": 8192,
        }

        headers = {"Content-Type": "application/json"}
        start = datetime.utcnow().isoformat()
        t0 = time.perf_counter()
        output = ""
        prompt_tokens = completion_tokens = total_tokens = tps = None
        error = ""
        try:
            async with aiohttp.ClientSession() as client:
                async with client.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        error = f"HTTP {resp.status}"
                        return results.append(
                            [session_id, start, "", "", "", "", "", "", error, ""]
                        )
                    first_token_time = None
                    token_count = 0
                    while True:
                        line_bytes = await resp.content.readline()
                        if not line_bytes:
                            break
                        line = line_bytes.decode().strip()
                        if line.startswith("data: "):
                            line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                payload = json.loads(line)
                                delta = payload["choices"][0]["delta"]
                                stats = payload["usage"] if "usage" in payload else {}
                                content = delta.get("content", "")
                                if content:
                                    if token_count == 0:
                                        first_token_time = time.perf_counter()
                                    token_count += 1
                                    output += content
                                # 통계 추출(지원시)
                                prompt_tokens = stats.get("prompt_tokens", prompt_tokens)
                                completion_tokens = stats.get(
                                    "completion_tokens", completion_tokens
                                )
                                total_tokens = stats.get("total_tokens", total_tokens)
                            except Exception as e:
                                error = f"parse:{e}"
                                break
                    t1 = time.perf_counter()
                    latency = t1 - t0
                    # 토큰수/TPS 계산
                    if completion_tokens is None:
                        completion_tokens = token_count
                    if latency > 0:  # 전체 latency 기준 TPS 계산
                        tps = completion_tokens / latency
                    else:
                        tps = 0.0
                    end = datetime.utcnow().isoformat()
                    gpu_util, mem_used = get_gpu_stats()
                    # output_head 분기 처리
                    if session_count == 1:
                        output_head = output.replace("\n", " ")
                    else:
                        output_head = output[:30].replace("\n", " ")
                    results.append(
                        [
                            session_id,
                            start,
                            end,
                            round(latency, 3),
                            prompt_tokens,
                            completion_tokens,
                            total_tokens,
                            round(tps, 2) if tps else "",
                            error,
                            gpu_util,
                            mem_used,
                            output_head,
                        ]
                    )
        except Exception as e:
            error = str(e)
            end = datetime.utcnow().isoformat()
            latency = time.perf_counter() - t0
            results.append([session_id, start, end, round(latency, 3), "", "", "", "", error, ""])


async def main(session_count: int):
    api_url = "http://localhost:15926/v1/chat/completions"
    semaphore = asyncio.Semaphore(session_count)
    results = []

    await asyncio.gather(
        *[
            test_single_session(f"session-{uuid.uuid4()}", api_url, semaphore, results, session_count)
            for _ in range(session_count)
        ]
    )

    # CSV로 기록
    output_filename = (
        f"data/stress_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_sess={session_count}.csv"
    )
    with open(output_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(fields)
        writer.writerows(results)
    print(f"\n\n✅ 스트레스 테스트 결과가 {output_filename}에 저장되었습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stress-test runner")
    parser.add_argument(
        "session_count",
        nargs="?",
        type=int,
        default=DEFAULT_SESSION_COUNT,
        help="동시 실행할 세션 수 (예: 10, 20, 40...) (기본값: 1)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.session_count))
