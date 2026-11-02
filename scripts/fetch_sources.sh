#!/usr/bin/env bash
# Download the source data into data-src/ (not committed: licences don't clearly allow redistribution).
#   - Tanzil Quran text (Uthmani), via a mirror with per-surah files and checksums
#   - Tafsir Al-Muyassar, from the tafsir_api mirror (sparse checkout of one edition)
#   - Qur'an QA 2023 Task A data (QPC passages, questions, qrels) — evaluation only
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data-src && cd data-src

clone() { [ -d "$2/.git" ] || GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 "$@"; }

clone https://github.com/semnan-university-ai/checksum-quran quran
clone https://github.com/ghazaleh-mahmoodi/quran-qa_2023_shared-task qqa23
if [ ! -d tafsir/.git ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 --filter=blob:none --sparse https://github.com/spa5k/tafsir_api tafsir
  git -C tafsir sparse-checkout set --no-cone '/tafsir/ar-tafsir-muyassar/' '/tafsir/editions.json'
fi
echo "Sources ready in data-src/"
