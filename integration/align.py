"""
Multi-source time alignment and provenance tracking.

Aligns flight log (ulog), MAVLink (pcap/text), ROS 2 bag, and video timestamps
using explicit time synchronization with provenance metadata.
"""

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
import bisect


@dataclass
class TimeSyncPoint:
    """A single synchronization point between two time sources."""

    source_a: str  # e.g., "ulog", "mavlink", "rosbag", "video"
    source_b: str
    timestamp_a: float  # Unix timestamp in source A's timebase
    timestamp_b: float  # Unix timestamp in source B's timebase
    confidence: float  # 0.0-1.0, quality of this sync point
    method: str  # "mavlink_timesync", "gps_pps", "ntp", "manual"
    provenance_a: str  # SHA-256 of source A file
    provenance_b: str  # SHA-256 of source B file


@dataclass
class TimeTransform:
    """Linear time transformation: t_b = scale * t_a + offset"""

    source_a: str
    source_b: str
    scale: float  # Typically 1.0 (same rate), or slightly different
    offset: float  # Seconds to add to A to get B
    r_squared: float  # Fit quality
    sync_points_used: int
    provenance: Dict[str, str]  # source_name -> SHA-256


@dataclass
class AlignedDataset:
    """A dataset with timestamps transformed to a common reference timebase."""

    source_name: str
    reference_timebase: str  # e.g., "ulog" (the master clock)
    transform: TimeTransform  # Transform from source to reference
    data: List[Dict[str, Any]]  # Records with 'timestamp' field transformed
    original_timebase: str  # Original timebase name
    provenance: str  # SHA-256 of source file


@dataclass
class ProvenanceRecord:
    """Complete provenance for an aligned dataset."""

    source_files: Dict[str, str]  # source_name -> file_path
    source_hashes: Dict[str, str]  # source_name -> SHA-256
    transforms: List[TimeTransform]
    alignment_timestamp: str  # ISO 8601 when alignment was computed
    alignment_code_version: str  # Git commit hash
    alignment_params: Dict[str, Any]


class TimeAligner:
    """Aligns multiple time-series datasets to a common reference timebase."""

    def __init__(
        self, reference_source: str = "ulog", alignment_code_version: Optional[str] = None
    ):
        self.reference_source = reference_source
        self.alignment_code_version = alignment_code_version or self._get_git_hash()
        self.sync_points: List[TimeSyncPoint] = []
        self.transforms: Dict[str, TimeTransform] = {}
        self.source_hashes: Dict[str, str] = {}
        self.source_files: Dict[str, str] = {}

    @staticmethod
    def _get_git_hash() -> str:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def add_source(self, source_name: str, file_path: str) -> None:
        """Register a source file and compute its hash."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Source file not found: {file_path}")
        self.source_files[source_name] = str(path.absolute())
        self.source_hashes[source_name] = self._compute_sha256(path)

    def add_sync_point(self, sync_point: TimeSyncPoint) -> None:
        """Add a synchronization point."""
        # Verify provenance matches registered sources
        if sync_point.source_a in self.source_hashes:
            assert (
                sync_point.provenance_a == self.source_hashes[sync_point.source_a]
            ), f"Provenance mismatch for {sync_point.source_a}"
        if sync_point.source_b in self.source_hashes:
            assert (
                sync_point.provenance_b == self.source_hashes[sync_point.source_b]
            ), f"Provenance mismatch for {sync_point.source_b}"

        self.sync_points.append(sync_point)

    def add_mavlink_timesync(
        self,
        source_a: str,
        source_b: str,
        timesync_msgs_a: List[Dict],
        timesync_msgs_b: List[Dict],
        max_pairs: int = 10,
    ) -> int:
        """
        Extract sync points from MAVLink TIMESYNC messages.

        TIMESYNC contains: tc1 (local), ts1 (remote) pairs.
        We match by sequence or closest timestamp.
        """
        # Group by sequence number if available
        pairs = []
        for msg_a in timesync_msgs_a:
            tc1_a = msg_a.get("tc1", 0)
            ts1_a = msg_a.get("ts1", 0)
            seq_a = msg_a.get("seq", 0)

            # Find matching message in source_b
            for msg_b in timesync_msgs_b:
                if msg_b.get("seq", 0) == seq_a:
                    tc1_b = msg_b.get("tc1", 0)
                    ts1_b = msg_b.get("ts1", 0)

                    # tc1 is local time (us), ts1 is remote time (us)
                    # For source_a: local=tc1_a, remote=ts1_a
                    # For source_b: local=tc1_b, remote=ts1_b
                    # If source_a sent TIMESYNC to source_b:
                    # source_a local = tc1_a, source_b local = tc1_b
                    # But we need to match the same event...

                    # Simplest: use tc1 as local timestamp for each
                    pairs.append(
                        TimeSyncPoint(
                            source_a=source_a,
                            source_b=source_b,
                            timestamp_a=tc1_a / 1e6,
                            timestamp_b=tc1_b / 1e6,
                            confidence=0.9,
                            method="mavlink_timesync",
                            provenance_a=self.source_hashes.get(source_a, ""),
                            provenance_b=self.source_hashes.get(source_b, ""),
                        )
                    )

        # If no sequence matching, fall back to timestamp proximity
        if not pairs and timesync_msgs_a and timesync_msgs_b:
            for msg_a in timesync_msgs_a[:max_pairs]:
                tc1_a = msg_a.get("tc1", 0) / 1e6
                # Find closest in time
                best_b = min(timesync_msgs_b, key=lambda m: abs(m.get("tc1", 0) / 1e6 - tc1_a))
                tc1_b = best_b.get("tc1", 0) / 1e6
                pairs.append(
                    TimeSyncPoint(
                        source_a=source_a,
                        source_b=source_b,
                        timestamp_a=tc1_a,
                        timestamp_b=tc1_b,
                        confidence=0.5,
                        method="mavlink_timesync_proximity",
                        provenance_a=self.source_hashes.get(source_a, ""),
                        provenance_b=self.source_hashes.get(source_b, ""),
                    )
                )

        for sp in pairs:
            self.add_sync_point(sp)

        return len(pairs)

    def add_gps_pps_sync(
        self,
        source_a: str,
        source_b: str,
        gps_msgs_a: List[Dict],
        gps_msgs_b: List[Dict],
        time_field: str = "time_usec",
    ) -> int:
        """
        Align using GPS time (both sources have GPS_RAW_INT with same time_usec).
        """
        pairs = []
        # Build lookup for source_b by time_usec
        gps_b_by_time = {msg.get(time_field, 0): msg for msg in gps_msgs_b}

        for msg_a in gps_msgs_a:
            t_a = msg_a.get(time_field, 0)
            if t_a in gps_b_by_time:
                msg_b = gps_b_by_time[t_a]
                pairs.append(
                    TimeSyncPoint(
                        source_a=source_a,
                        source_b=source_b,
                        timestamp_a=t_a / 1e6,
                        timestamp_b=msg_b.get(time_field, 0) / 1e6,
                        confidence=0.95,
                        method="gps_time_match",
                        provenance_a=self.source_hashes.get(source_a, ""),
                        provenance_b=self.source_hashes.get(source_b, ""),
                    )
                )

        for sp in pairs:
            self.add_sync_point(sp)

        return len(pairs)

    def compute_transforms(self, min_confidence: float = 0.5) -> Dict[str, TimeTransform]:
        """
        Compute linear time transforms from each source to reference.
        Uses all sync points involving the reference source.
        """
        # Group sync points by (source_a, source_b) where one is reference
        ref_points = defaultdict(list)  # other_source -> List[(t_ref, t_other, conf)]

        for sp in self.sync_points:
            if sp.confidence < min_confidence:
                continue
            if sp.source_a == self.reference_source:
                ref_points[sp.source_b].append((sp.timestamp_a, sp.timestamp_b, sp.confidence))
            elif sp.source_b == self.reference_source:
                ref_points[sp.source_a].append((sp.timestamp_b, sp.timestamp_a, sp.confidence))

        transforms = {}
        for other_source, points in ref_points.items():
            if len(points) < 2:
                continue

            # Weighted linear regression: t_ref = scale * t_other + offset
            # Weight by confidence
            weights = [p[2] for p in points]
            t_ref = [p[0] for p in points]
            t_other = [p[1] for p in points]

            # Simple weighted linear fit
            w_sum = sum(weights)
            w_t_ref = sum(w * r for w, r in zip(weights, t_ref))
            w_t_other = sum(w * o for w, o in zip(weights, t_other))
            w_t_ref2 = sum(w * r * r for w, r in zip(weights, t_ref))
            w_t_other2 = sum(w * o * o for w, o in zip(weights, t_other))
            w_t_ref_other = sum(w * r * o for w, r, o in zip(weights, t_ref, t_other))

            # Solve: scale * sum(w*t_other^2) + offset * sum(w*t_other) = sum(w*t_ref*t_other)
            #        scale * sum(w*t_other)   + offset * sum(w)       = sum(w*t_ref)
            denom = w_t_other2 * w_sum - w_t_other * w_t_other
            if abs(denom) < 1e-12:
                continue

            scale = (w_t_ref_other * w_sum - w_t_ref * w_t_other) / denom
            offset = (w_t_ref * w_t_other2 - w_t_ref_other * w_t_other) / denom

            # Compute R-squared
            t_ref_pred = [scale * o + offset for o in t_other]
            ss_res = sum(w * (r - p) ** 2 for w, r, p in zip(weights, t_ref, t_ref_pred))
            t_ref_mean = w_t_ref / w_sum
            ss_tot = sum(w * (r - t_ref_mean) ** 2 for w, r in zip(weights, t_ref))
            r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            transform = TimeTransform(
                source_a=other_source,
                source_b=self.reference_source,
                scale=scale,
                offset=offset,
                r_squared=r_squared,
                sync_points_used=len(points),
                provenance={
                    other_source: self.source_hashes.get(other_source, ""),
                    self.reference_source: self.source_hashes.get(self.reference_source, ""),
                },
            )
            transforms[other_source] = transform

        self.transforms = transforms
        return transforms

    def align_dataset(
        self, source_name: str, data: List[Dict], timestamp_field: str = "timestamp"
    ) -> AlignedDataset:
        """
        Transform dataset timestamps to reference timebase.

        Args:
            source_name: Name of the source (must have transform computed)
            data: List of records with timestamp field
            timestamp_field: Field name containing timestamp (seconds)

        Returns:
            AlignedDataset with transformed timestamps
        """
        if source_name == self.reference_source:
            transform = TimeTransform(
                source_a=source_name,
                source_b=source_name,
                scale=1.0,
                offset=0.0,
                r_squared=1.0,
                sync_points_used=0,
                provenance={source_name: self.source_hashes.get(source_name, "")},
            )
        else:
            if source_name not in self.transforms:
                raise ValueError(
                    f"No transform computed for {source_name}. Run compute_transforms() first."
                )
            transform = self.transforms[source_name]

        # Apply transform
        aligned_data = []
        for record in data:
            if timestamp_field not in record:
                continue
            t_orig = record[timestamp_field]
            t_aligned = transform.scale * t_orig + transform.offset
            new_record = record.copy()
            new_record[timestamp_field] = t_aligned
            new_record["_original_timestamp"] = t_orig
            new_record["_timebase"] = self.reference_source
            aligned_data.append(new_record)

        return AlignedDataset(
            source_name=source_name,
            reference_timebase=self.reference_source,
            transform=transform,
            data=aligned_data,
            original_timebase=source_name,
            provenance=self.source_hashes.get(source_name, ""),
        )

    def align_multiple(
        self, datasets: Dict[str, List[Dict]], timestamp_fields: Dict[str, str] = None
    ) -> Dict[str, AlignedDataset]:
        """Align multiple datasets at once."""
        if timestamp_fields is None:
            timestamp_fields = {k: "timestamp" for k in datasets}

        self.compute_transforms()
        return {
            name: self.align_dataset(name, data, timestamp_fields.get(name, "timestamp"))
            for name, data in datasets.items()
        }

    def get_provenance_record(self, alignment_params: Dict = None) -> ProvenanceRecord:
        """Get complete provenance record for this alignment."""
        return ProvenanceRecord(
            source_files=self.source_files,
            source_hashes=self.source_hashes,
            transforms=list(self.transforms.values()),
            alignment_timestamp=datetime.utcnow().isoformat() + "Z",
            alignment_code_version=self.alignment_code_version,
            alignment_params=alignment_params or {},
        )

    def save_provenance(self, output_path: str, alignment_params: Dict = None) -> None:
        """Save provenance record to JSON."""
        prov = self.get_provenance_record(alignment_params)
        with open(output_path, "w") as f:
            json.dump(asdict(prov), f, indent=2, default=str)

    def export_aligned_data(self, aligned: Dict[str, AlignedDataset], output_dir: str) -> None:
        """Export aligned datasets to JSON files."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        for name, dataset in aligned.items():
            out_file = out_path / f"{name}_aligned.json"
            with open(out_file, "w") as f:
                json.dump(
                    {
                        "source_name": dataset.source_name,
                        "reference_timebase": dataset.reference_timebase,
                        "transform": asdict(dataset.transform),
                        "original_timebase": dataset.original_timebase,
                        "provenance": dataset.provenance,
                        "data": dataset.data,
                    },
                    f,
                    indent=2,
                    default=str,
                )


def find_common_time_range(aligned_datasets: Dict[str, AlignedDataset]) -> Tuple[float, float]:
    """Find overlapping time range across all aligned datasets."""
    all_starts = []
    all_ends = []

    for dataset in aligned_datasets.values():
        if not dataset.data:
            continue
        timestamps = [d.get("timestamp", 0) for d in dataset.data]
        if timestamps:
            all_starts.append(min(timestamps))
            all_ends.append(max(timestamps))

    if not all_starts:
        return (0.0, 0.0)

    return (max(all_starts), min(all_ends))


def resample_to_common_grid(
    aligned_datasets: Dict[str, AlignedDataset],
    dt: float = 0.1,  # 10Hz
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> Dict[str, List[Dict]]:
    """
    Resample all aligned datasets to a common time grid.
    Uses linear interpolation for numeric fields.
    """
    if start is None or end is None:
        start, end = find_common_time_range(aligned_datasets)

    grid = []
    t = start
    while t <= end:
        grid.append(t)
        t += dt

    result = {}
    for name, dataset in aligned_datasets.items():
        if not dataset.data:
            result[name] = []
            continue

        # Group by field
        fields = set()
        for d in dataset.data:
            fields.update(d.keys())
        fields.discard("timestamp")
        fields.discard("_original_timestamp")
        fields.discard("_timebase")

        # Build interpolation for each field
        resampled = []
        for t_target in grid:
            record = {"timestamp": t_target}
            for field in fields:
                # Find surrounding points
                values = [
                    (d["timestamp"], d.get(field))
                    for d in dataset.data
                    if field in d and d[field] is not None
                ]
                if not values:
                    record[field] = None
                    continue

                values.sort()
                times = [v[0] for v in values]
                vals = [v[1] for v in values]

                if t_target <= times[0]:
                    record[field] = vals[0]
                elif t_target >= times[-1]:
                    record[field] = vals[-1]
                else:
                    # Linear interpolation
                    i = bisect.bisect_left(times, t_target)
                    t0, t1 = times[i - 1], times[i]
                    v0, v1 = vals[i - 1], vals[i]
                    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                        alpha = (t_target - t0) / (t1 - t0)
                        record[field] = v0 + alpha * (v1 - v0)
                    else:
                        record[field] = v0
            resampled.append(record)

        result[name] = resampled

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Align multi-source flight data")
    parser.add_argument("--ulog", help="PX4 ulog file (reference)")
    parser.add_argument("--mavlink", help="MAVLink log file")
    parser.add_argument("--rosbag", help="ROS 2 bag directory")
    parser.add_argument("--output-dir", default="aligned_output", help="Output directory")
    parser.add_argument("--dt", type=float, default=0.1, help="Resample interval (s)")

    args = parser.parse_args()

    # This would need actual data loading - placeholder for CLI structure
    print("TimeAligner CLI - implement data loading for your sources")
    print(f"Reference: {args.ulog}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
