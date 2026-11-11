#!/usr/bin/env python3
"""
데이터셋 아카이브 생성 스크립트
처리된 데이터셋을 tar.zst로 압축하고 SHA256 체크섬 생성
"""

import subprocess
import hashlib
from pathlib import Path
import sys

DATASETS = {
    "idf_ds": "~/data/drone_datasets/processed/idf_ds",
    "ign_fixed_wing": "~/data/drone_datasets/processed/ign_fixed_wing",
    "uzh_fpv": "~/data/drone_datasets/processed/uzh_fpv",
    "fpv_analog": "/tmp/fpv_analog_full3",
    "fixed_wing_attitude": "~/data/drone_datasets/processed/fixed_wing_attitude",
    "navigation_datasets": "~/data/drone_datasets/navigation_datasets",
}

OUTPUT_DIR = Path("~/q250_datasets").expanduser()

ZSTD_CMD = "/usr/local/bin/zstd"


def create_archive(src: Path, dst: Path) -> bool:
    """tar.zst로 압축"""
    src = Path(src).expanduser()
    if not src.exists():
        print(f"  ⚠️  소스 없음: {src}")
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  압축 중: {src.name} -> {dst.name}")

    try:
        # tar + zstd 압축 (멀티스레드, 전체 경로 지정)
        result = subprocess.run(
            [
                "tar",
                "-I",
                f"{ZSTD_CMD} -T0",
                "-cf",
                str(dst),
                "-C",
                str(src.parent),
                src.name,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        print(f"  ✅ 완료: {dst} ({dst.stat().st_size/1e9:.2f} GB)")
        return True
    except subprocess.TimeoutExpired:
        print(f"  ❌ 타임아웃: {src.name}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 압축 실패: {e.stderr}")
        return False


def generate_sha256(filepath: Path) -> str:
    """SHA256 체크섬 생성"""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Q250-V3-Opti 데이터셋 아카이브 생성")
    print("=" * 60)

    results = {}
    for name, src in DATASETS.items():
        print(f"\n[{name}]")
        dst = OUTPUT_DIR / f"q250_{name}_v1.tar.zst"
        success = create_archive(Path(src), dst)
        results[name] = success

    # SHA256 체크섬 생성
    print("\n" + "=" * 60)
    print("SHA256 체크섬 생성")
    print("=" * 60)

    checksums = {}
    for name in DATASETS:
        dst = OUTPUT_DIR / f"q250_{name}_v1.tar.zst"
        if dst.exists():
            checksum = generate_sha256(dst)
            checksums[name] = checksum
            (dst.with_suffix(".tar.zst.sha256")).write_text(f"{checksum}  {dst.name}\n")
            print(f"  {name}: {checksum}")

    # 통합 체크섬 파일
    all_checksums = "\n".join(f"{v}  q250_{k}_v1.tar.zst" for k, v in checksums.items())
    (OUTPUT_DIR / "SHA256SUMS").write_text(all_checksums + "\n")
    print(f"\n통합 체크섬 저장: {OUTPUT_DIR}/SHA256SUMS")

    # 요약
    print("\n" + "=" * 60)
    print("생성 완료 요약")
    print("=" * 60)
    for name, success in results.items():
        status = "✅" if success else "❌"
        size = ""
        dst = OUTPUT_DIR / f"q250_{name}_v1.tar.zst"
        if dst.exists():
            size = f" ({dst.stat().st_size/1e9:.2f} GB)"
        print(f"  {status} {name}{size}")

    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
