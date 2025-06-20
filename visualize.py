import pandas as pd
import matplotlib.pyplot as plt
import glob, os, re
from matplotlib.dates import date2num
from datetime import datetime
import matplotlib

# 1. CSV 파일 목록 불러오기 (data/ 폴더 하위)
csv_files = sorted(glob.glob("data/stress_test_*_sess=*.csv"))

# 결과 저장용
summary_list = []

for f in csv_files:
    # 세션 수 추출
    m = re.search(r"sess=(\d+)", f)
    session_count = int(m.group(1)) if m else None

    df = pd.read_csv(f)
    # 수치형 보정
    df["latency_s"] = pd.to_numeric(df["latency_s"], errors="coerce")
    df["gpu_util_percent"] = pd.to_numeric(df["gpu_util_percent"], errors="coerce")
    df["gpu_memory_mib"] = pd.to_numeric(df["gpu_memory_mib"], errors="coerce")
    df["tps"] = pd.to_numeric(df["tps"], errors="coerce")
    # 평균값 계산
    latency_mean = df["latency_s"].mean()
    gpu_mean = df["gpu_util_percent"].mean()
    mem_mean = df["gpu_memory_mib"].mean()
    tps_mean = df["tps"].mean()
    error_count = df["error"].notnull().sum()
    summary_list.append(
        {
            "session_count": session_count,
            "latency_mean": latency_mean,
            "gpu_util_mean": gpu_mean,
            "gpu_mem_mean": mem_mean,
            "tps_mean": tps_mean,
            "error_count": error_count,
        }
    )

# 1-1. 세션 수별 요약 시각화 -------------------
summary = pd.DataFrame(summary_list).sort_values("session_count")

plt.figure(figsize=(20, 5))

plt.subplot(1, 4, 1)
plt.plot(summary["session_count"].values, summary["latency_mean"].values, marker="o")
for x, y in zip(summary["session_count"].values, summary["latency_mean"].values):
    plt.text(x, y, f"{y:.2f}", ha="center", va="bottom", fontsize=8)
plt.xlabel("concurrent sessions")
plt.ylabel("mean Latency (s)")
plt.title("Average Latency")

plt.subplot(1, 4, 2)
plt.plot(
    summary["session_count"].values, summary["gpu_util_mean"].values, marker="s", color="orange"
)
for x, y in zip(summary["session_count"].values, summary["gpu_util_mean"].values):
    plt.text(x, y, f"{y:.2f}", ha="center", va="bottom", fontsize=8)
plt.xlabel("concurrent sessions")
plt.ylabel("mean GPU Utilization (%)")
plt.title("GPU Utilization")

plt.subplot(1, 4, 3)
plt.plot(summary["session_count"].values, summary["gpu_mem_mean"].values, marker="^", color="green")
for x, y in zip(summary["session_count"].values, summary["gpu_mem_mean"].values):
    plt.text(x, y, f"{y:.2f}", ha="center", va="bottom", fontsize=8)
plt.xlabel("concurrent sessions")
plt.ylabel("mean GPU Memory (MiB)")
plt.title("GPU Memory")

plt.subplot(1, 4, 4)
plt.plot(summary["session_count"].values, summary["tps_mean"].values, marker="d", color="purple")
for x, y in zip(summary["session_count"].values, summary["tps_mean"].values):
    plt.text(x, y, f"{y:.2f}", ha="center", va="bottom", fontsize=8)
plt.xlabel("concurrent sessions")
plt.ylabel("mean TPS (tokens/sec)")
plt.title("Tokens per Second (TPS)")

plt.tight_layout()
plt.savefig("images/stress_test_summary.png")

plt.figure(figsize=(6, 4))
error_rate = (summary["error_count"] / summary["session_count"] * 100).values
plt.plot(
    summary["session_count"].values,
    error_rate,
    marker="x",
    color="red",
)
for x, y in zip(summary["session_count"].values, error_rate):
    plt.text(x, y, f"{y:.2f}%", ha="center", va="bottom", fontsize=8)
plt.xlabel("concurrent sessions")
plt.ylabel("Error Rate (%)")
plt.title("Error Rate by Session Count")
plt.grid(True)
plt.tight_layout()
plt.savefig("images/stress_test_error_rate.png")

# 2. 각 실행의 세션 Gantt-style 타임라인 ----------


def plot_session_timeline(csv_path, title=None):
    df = pd.read_csv(csv_path)
    # 시작/종료시간을 datetime으로 변환
    df["start_dt"] = pd.to_datetime(df["start_time"])
    df["end_dt"] = pd.to_datetime(df["end_time"])
    # 세션별 막대 (y축은 index)
    fig, ax = plt.subplots(figsize=(12, 0.3 * len(df) + 2))
    for i, row in df.iterrows():
        ax.plot([row["start_dt"], row["end_dt"]], [i, i], color="blue")
        ax.scatter(date2num(row["start_dt"]), i, color="green", s=10)
        ax.scatter(date2num(row["end_dt"]), i, color="red", s=10)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["session_id"].values, fontsize=7)
    ax.set_xlabel("Time")
    ax.set_title(title or os.path.basename(csv_path))
    plt.tight_layout()
    # plt.show()
    plt.savefig("images/" + csv_path.split("/")[-1].replace(".csv", "_timeline.png"))


for f in csv_files:
    plot_session_timeline(f, title=f"Session Timeline - {os.path.basename(f)}")