#!/usr/bin/env bash
# Sequentially analyze remaining assets with the new pipeline.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p logs

PODCASTS=(
  播客-2 播客-3 播客-4 播客-5 播客-6 播客-7 播客-8 播客-9
  播客-10 播客-11 播客-12 播客-13 播客-14 播客-15
)

VIDEOS=(
  helloai-native-design
  ai-native-时代的设计美学与交互体验迁移
  desiagn-x-ai-工作范式进化审美意图与真实性的动态博弈
  从-design-到-buildagent-时代体验设计师的新边界
  从数据到智慧的认知阶梯
  如何用-ai-放大个人能力
  看见与不被看见-千问智能眼镜近眼交互设计师初探
)

LOG=logs/batch_analyze.log
echo "==== batch start $(date) ====" | tee -a "$LOG"

for id in "${PODCASTS[@]}"; do
  echo "" | tee -a "$LOG"
  echo ">>>> PODCAST $id $(date)" | tee -a "$LOG"
  python scripts/analyze_one.py --asset "$id" 2>&1 | tee -a "$LOG" || echo "FAILED $id" | tee -a "$LOG"
done

for id in "${VIDEOS[@]}"; do
  echo "" | tee -a "$LOG"
  echo ">>>> VIDEO $id $(date)" | tee -a "$LOG"
  python scripts/analyze_one.py --asset "$id" 2>&1 | tee -a "$LOG" || echo "FAILED $id" | tee -a "$LOG"
done

echo "==== batch end $(date) ====" | tee -a "$LOG"
