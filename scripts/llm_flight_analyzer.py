#!/usr/bin/env python3
"""
LLM-Enhanced Flight Log Analyzer for Q250-V3-Opti

Extends the base flight log analyzer with LLM-powered natural language
report generation, anomaly detection, and intelligent recommendations.
"""

import json
import os
import sqlite3
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class FlightAnalysisResult:
    flight_id: str
    summary: str
    ekf2_health: Dict
    vio_quality: Dict
    gps_quality: Dict
    avoidance_performance: Dict
    silvus_link: Dict
    battery_health: Dict
    anomalies: List[Dict]
    recommendations: List[str]
    llm_narrative: str
    timestamp: str


class LLMFlightAnalyzer:
    """LLM-enhanced flight log analyzer"""

    def __init__(
        self, db_path: str, llm_provider: str = "openai", llm_model: str = "gpt-4o"
    ):
        self.db_path = db_path
        self.llm_provider = llm_provider
        self.llm_model = llm_model

        # Initialize LLM client
        self.llm_client = self._create_llm_client()

        # System prompt for flight analysis
        self.system_prompt = self._load_system_prompt()

    def _create_llm_client(self):
        if self.llm_provider == "openai" and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                return openai.OpenAI(api_key=api_key)
        elif self.llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                return anthropic.Anthropic(api_key=api_key)
        return None

    def _load_system_prompt(self) -> str:
        return """You are an expert drone flight analyst for the Q250-V3-Opti autonomous drone system.

## Your Role
Analyze flight data and generate comprehensive natural language reports with actionable insights.

## System Context
- Drone: Q250-V3-Opti (Pixhawk 6C Mini + Jetson Orin + Silvus Mesh)
- Flight Controller: PX4 v1.15
- Navigation: VIO + EKF2 (No GPS indoor), Fake GPS for global position
- Communication: Silvus MN-MIMO (80-120 Mbps, 3-8ms RTT, up to 20-50km)
- Obstacle Avoidance: Depth camera + LiDAR + TEB Local Planner
- Coordinate Frame: ENU (ROS) ↔ NED (PX4) conversion handled externally

## Analysis Focus Areas
1. **EKF2 Estimator Health**: Innovation statistics, sensor fusion quality, consistency
2. **VIO Quality**: Drift rate, tracking stability, covariance realism
3. **GPS/Fake GPS Quality**: Innovation, fix type, satellite count, accuracy
4. **Obstacle Avoidance**: Trigger rate, success rate, minimum distances, planner performance
5. **Silvus Link Quality**: RSSI, packet loss, RTT, topology changes
6. **Battery Health**: Voltage sag, current draw, capacity estimation
7. **Flight Modes**: Time in each mode, transitions, OFFBOARD stability
7. **Anomalies**: Unexpected events, parameter deviations, safety violations

## Output Format
Provide a natural language narrative report with:
- Executive summary (2-3 sentences)
- Detailed findings per focus area
- Specific anomalies with timestamps
- Concrete, actionable recommendations with priority
- Parameter tuning suggestions with specific values

## Tone
Professional, technical, actionable. Use specific numbers and timestamps.
Avoid vague statements - be precise with metrics and thresholds.
"""

    def analyze_flight(self, flight_id: str) -> FlightAnalysisResult:
        """Analyze a flight and generate comprehensive report"""

        # Fetch flight data from database
        flight_data = self._fetch_flight_data(flight_id)

        if not flight_data:
            raise ValueError(f"Flight {flight_id} not found in database")

        # Compute metrics
        metrics = self._compute_metrics(flight_data)

        # Detect anomalies
        anomalies = self._detect_anomalies(flight_data, metrics)

        # Generate LLM narrative
        llm_narrative = self._generate_llm_narrative(flight_id, metrics, anomalies)

        # Generate recommendations
        recommendations = self._generate_recommendations(metrics, anomalies)

        return FlightAnalysisResult(
            flight_id=flight_id,
            summary=metrics.get("summary", ""),
            ekf2_health=metrics.get("ekf2_health", {}),
            vio_quality=metrics.get("vio_quality", {}),
            gps_quality=metrics.get("gps_quality", {}),
            avoidance_performance=metrics.get("avoidance_performance", {}),
            silvus_link=metrics.get("silvus_link", {}),
            battery_health=metrics.get("battery_health", {}),
            anomalies=anomalies,
            recommendations=recommendations,
            llm_narrative=llm_narrative,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def _fetch_flight_data(self, flight_id: str) -> Optional[Dict]:
        """Fetch all flight data from database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get flight metadata
        cursor.execute("SELECT * FROM flights WHERE flight_id = ?", (flight_id,))
        flight_row = cursor.fetchone()
        if not flight_row:
            return None

        flight_data = {
            "metadata": dict(flight_row),
            "ekf2_innovations": [],
            "vehicle_local_position": [],
            "vehicle_global_position": [],
            "vehicle_attitude": [],
            "actuator_outputs": [],
            "battery_status": [],
            "rc_channels": [],
            "estimator_status": [],
            "distance_sensor": [],
            "optical_flow": [],
            "mavlink_messages": [],
            "silvus_link_quality": [],
            "flight_events": [],
        }

        # Fetch all related data
        tables = [
            "ekf2_innovations",
            "vehicle_local_position",
            "vehicle_global_position",
            "vehicle_attitude",
            "actuator_outputs",
            "battery_status",
            "rc_channels",
            "estimator_status",
            "distance_sensor",
            "optical_flow",
            "mavlink_messages",
            "silvus_link_quality",
            "flight_events",
        ]

        for table in tables:
            cursor.execute(
                f"SELECT * FROM {table} WHERE flight_id = ? ORDER BY timestamp",
                (flight_id,),
            )
            rows = cursor.fetchall()
            flight_data[table] = [dict(row) for row in rows]

        conn.close()
        return flight_data

    def _compute_metrics(self, flight_data: Dict) -> Dict:
        """Compute quantitative metrics from flight data"""
        metrics = {}

        # EKF2 Health
        ekf2 = flight_data.get("ekf2_innovations", [])
        if ekf2:
            pos_innov = [
                [
                    r.get("pos_innov_n", 0),
                    r.get("pos_innov_e", 0),
                    r.get("pos_innov_d", 0),
                ]
                for r in ekf2
            ]
            vel_innov = [
                [
                    r.get("vel_innov_n", 0),
                    r.get("vel_innov_e", 0),
                    r.get("vel_innov_d", 0),
                ]
                for r in ekf2
            ]

            import numpy as np

            pos_innov_arr = np.array(pos_innov)
            vel_innov_arr = np.array(vel_innov)

            metrics["ekf2_health"] = {
                "pos_innov_mean": np.mean(pos_innov_arr, axis=0).tolist(),
                "pos_innov_std": np.std(pos_innov_arr, axis=0).tolist(),
                "vel_innov_mean": np.mean(vel_innov_arr, axis=0).tolist(),
                "vel_innov_std": np.std(vel_innov_arr, axis=0).tolist(),
                "pos_3sigma_violation_rate": self._compute_3sigma_violations(
                    pos_innov_arr
                ),
                "vel_3sigma_violation_rate": self._compute_3sigma_violations(
                    vel_innov_arr
                ),
                "sample_count": len(ekf2),
            }

        # VIO Quality (from local position vs global if available)
        local_pos = flight_data.get("vehicle_local_position", [])
        global_pos = flight_data.get("vehicle_global_position", [])

        if local_pos:
            positions = np.array(
                [[r.get("x", 0), r.get("y", 0), r.get("z", 0)] for r in local_pos]
            )
            if len(positions) > 1:
                # Compute drift rate (position change during hover/loiter)
                drift = np.mean(np.linalg.norm(np.diff(positions, axis=0), axis=1))
                metrics["vio_quality"] = {
                    "avg_drift_rate_m_s": float(drift),
                    "position_std": np.std(positions, axis=0).tolist(),
                    "sample_count": len(local_pos),
                }

        # GPS/Fake GPS Quality
        if global_pos:
            gps_data = [
                (
                    r.get("eph", 0),
                    r.get("epv", 0),
                    r.get("fix_type", 0),
                    r.get("satellites_visible", 0),
                )
                for r in global_pos
            ]
            if gps_data:
                eph_vals = [d[0] for d in gps_data]
                epv_vals = [d[1] for d in gps_data]
                fix_types = [d[2] for d in gps_data]
                sats = [d[3] for d in gps_data]

                metrics["gps_quality"] = {
                    "avg_horizontal_accuracy": float(np.mean(eph_vals)),
                    "avg_vertical_accuracy": float(np.mean(epv_vals)),
                    "fix_type_mode": (
                        int(np.bincount(fix_types).argmax()) if fix_types else 0
                    ),
                    "avg_satellites": float(np.mean(sats)),
                    "fix_type_distribution": {
                        str(i): fix_types.count(i) for i in set(fix_types)
                    },
                    "sample_count": len(global_pos),
                }

        # Obstacle Avoidance Performance
        events = flight_data.get("flight_events", [])
        ca_events = [
            e
            for e in events
            if e.get("event_type") in ["avoidance", "obstacle_detected", "ca_triggered"]
        ]
        metrics["avoidance_performance"] = {
            "total_triggers": len(ca_events),
            "successful_stops": len(
                [
                    e
                    for e in ca_events
                    if e.get("description", "").lower().find("stop") >= 0
                ]
            ),
            "avoidance_rate": len(ca_events) / max(1, len(events)) if events else 0,
            "event_types": {
                e.get("event_type", "unknown"): events.count(e)
                for e in set(e.get("event_type", "unknown") for e in events)
            },
        }

        # Silvus Link Quality
        silvus = flight_data.get("silvus_link_quality", [])
        if silvus:
            rssi = [
                r.get("rssi_dbm", -100) for r in silvus if r.get("rssi_dbm") is not None
            ]
            loss = [
                r.get("packet_loss_pct", 100)
                for r in silvus
                if r.get("packet_loss_pct") is not None
            ]
            rtt = [r.get("rtt_ms", 1000) for r in silvus if r.get("rtt_ms") is not None]

            metrics["silvus_link"] = {
                "avg_rssi_dbm": float(np.mean(rssi)) if rssi else -100,
                "min_rssi_dbm": float(np.min(rssi)) if rssi else -100,
                "avg_packet_loss_pct": float(np.mean(loss)) if loss else 100,
                "max_packet_loss_pct": float(np.max(loss)) if loss else 100,
                "avg_rtt_ms": float(np.mean(rtt)) if rtt else 1000,
                "degradation_events": len([l for l in loss if l > 10]),
                "sample_count": len(silvus),
            }

        # Battery Health
        battery = flight_data.get("battery_status", [])
        if battery:
            voltages = [
                r.get("voltage_v", 0) for r in battery if r.get("voltage_v", 0) > 0
            ]
            currents = [
                r.get("current_a", 0) for r in battery if r.get("current_a", 0) > 0
            ]

            metrics["battery_health"] = {
                "min_voltage_v": float(np.min(voltages)) if voltages else 0,
                "avg_voltage_v": float(np.mean(voltages)) if voltages else 0,
                "voltage_sag_v": (
                    float(np.max(voltages) - np.min(voltages))
                    if len(voltages) > 1
                    else 0
                ),
                "avg_current_a": float(np.mean(currents)) if currents else 0,
                "max_current_a": float(np.max(currents)) if currents else 0,
                "sample_count": len(battery),
            }

        # Summary
        metrics["summary"] = self._generate_summary(metrics)

        return metrics

    def _compute_3sigma_violations(self, innovations: np.ndarray) -> float:
        """Compute 3-sigma violation rate"""
        if len(innovations) == 0:
            return 0.0
        std = np.std(innovations, axis=0)
        mean = np.mean(innovations, axis=0)
        violations = np.sum(np.abs(innovations - mean) > 3 * std, axis=0)
        total = innovations.shape[0] * innovations.shape[1]
        return float(np.sum(violations) / total) if total > 0 else 0.0

    def _generate_summary(self, metrics: Dict) -> str:
        parts = []
        if "ekf2_health" in metrics:
            ekf = metrics["ekf2_health"]
            parts.append(
                f"EKF2 3σ violation: {ekf.get('pos_3sigma_violation_rate', 0)*100:.1f}%"
            )
        if "vio_quality" in metrics:
            vio = metrics["vio_quality"]
            parts.append(f"VIO drift: {vio.get('avg_drift_rate_m_s', 0)*100:.1f} cm/s")
        if "gps_quality" in metrics:
            gps = metrics["gps_quality"]
            parts.append(
                f"GPS: {gps.get('fix_type_mode', 0)} fix, {gps.get('avg_satellites', 0):.0f} sats"
            )
        if "silvus_link" in metrics:
            silvus = metrics["silvus_link"]
            parts.append(
                f"Silvus: {silvus.get('avg_rssi_dbm', 0):.0f} dBm, {silvus.get('avg_packet_loss_pct', 0):.1f}% loss"
            )
        return "; ".join(parts) if parts else "No metrics available"

    def _detect_anomalies(self, flight_data: Dict, metrics: Dict) -> List[Dict]:
        """Detect anomalies in flight data"""
        anomalies = []

        # EKF2 innovations
        ekf = metrics.get("ekf2_health", {})
        if ekf.get("pos_3sigma_violation_rate", 0) > 0.05:
            anomalies.append(
                {
                    "type": "ekf2_innovation_excess",
                    "severity": "high",
                    "message": f"EKF2 position innovation 3σ violation rate {ekf['pos_3sigma_violation_rate']*100:.1f}% exceeds 5% threshold",
                    "metric": "pos_3sigma_violation_rate",
                    "value": ekf["pos_3sigma_violation_rate"],
                    "threshold": 0.05,
                }
            )

        # VIO drift
        vio = metrics.get("vio_quality", {})
        if vio.get("avg_drift_rate_m_s", 0) > 0.05:  # 5 cm/s
            anomalies.append(
                {
                    "type": "vio_excessive_drift",
                    "severity": "medium",
                    "message": f"VIO drift rate {vio['avg_drift_rate_m_s']*100:.1f} cm/s exceeds 5 cm/s threshold",
                    "metric": "avg_drift_rate_m_s",
                    "value": vio["avg_drift_rate_m_s"],
                    "threshold": 0.05,
                }
            )

        # GPS quality
        gps = metrics.get("gps_quality", {})
        if gps.get("avg_horizontal_accuracy", 999) > 5.0:
            anomalies.append(
                {
                    "type": "gps_poor_accuracy",
                    "severity": "medium",
                    "message": f"GPS horizontal accuracy {gps['avg_horizontal_accuracy']:.1f}m exceeds 5m",
                    "metric": "avg_horizontal_accuracy",
                    "value": gps["avg_horizontal_accuracy"],
                    "threshold": 5.0,
                }
            )

        # Silvus link
        silvus = metrics.get("silvus_link", {})
        if silvus.get("avg_packet_loss_pct", 0) > 10:
            anomalies.append(
                {
                    "type": "silvus_high_loss",
                    "severity": "high",
                    "message": f"Silvus packet loss {silvus['avg_packet_loss_pct']:.1f}% exceeds 10%",
                    "metric": "avg_packet_loss_pct",
                    "value": silvus["avg_packet_loss_pct"],
                    "threshold": 10.0,
                }
            )

        # Battery voltage sag
        battery = metrics.get("battery_health", {})
        if battery.get("voltage_sag_v", 0) > 1.0:
            anomalies.append(
                {
                    "type": "battery_voltage_sag",
                    "severity": "medium",
                    "message": f"Battery voltage sag {battery['voltage_sag_v']:.2f}V exceeds 1.0V",
                    "metric": "voltage_sag_v",
                    "value": battery["voltage_sag_v"],
                    "threshold": 1.0,
                }
            )

        # Flight events
        events = flight_data.get("flight_events", [])
        for event in events:
            if event.get("severity") == "critical":
                anomalies.append(
                    {
                        "type": "flight_event_critical",
                        "severity": "critical",
                        "message": f"Critical flight event: {event.get('event_type', 'unknown')}: {event.get('description', '')}",
                        "timestamp": event.get("timestamp"),
                        "event_type": event.get("event_type"),
                    }
                )

        return anomalies

    def _generate_llm_narrative(
        self, flight_id: str, metrics: Dict, anomalies: List[Dict]
    ) -> str:
        """Generate natural language narrative using LLM"""

        if self.llm_client is None:
            return self._generate_fallback_narrative(metrics, anomalies)

        # Prepare context for LLM
        context = {
            "flight_id": flight_id,
            "metrics_summary": self._metrics_to_text(metrics),
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
        }

        user_prompt = f"""
Analyze flight {flight_id} and generate a professional flight analysis report.

## Metrics Summary
{self._metrics_to_text(metrics)}

## Anomalies Detected ({len(anomalies)})
{json.dumps(anomalies, indent=2)}

## Required Report Sections
1. **Executive Summary** (2-3 sentences)
2. **EKF2 Estimator Health** - innovation statistics, sensor fusion quality
3. **VIO Quality** - drift rate, tracking stability
4. **GPS/Fake GPS Quality** - innovation, fix type, accuracy
4. **Obstacle Avoidance** - trigger rate, success rate, minimum distances
5. **Silvus Link Quality** - RSSI, packet loss, RTT, topology
5. **Battery Health** - voltage sag, current draw
6. **Anomalies & Safety Events** - specific events with timestamps
7. **Recommendations** - specific, actionable, prioritized (parameter values, procedures)

## Style
- Professional, technical, precise
- Use specific numbers and timestamps
- Prioritize safety-critical findings
- Include specific parameter values for tuning recommendations
"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )
            return response.choices[0].message.content
        except Exception as e:
            self.get_logger().warn(f"LLM generation failed: {e}")
            return self._generate_fallback_narrative(metrics, anomalies)

    def _metrics_to_text(self, metrics: Dict) -> str:
        lines = []
        for category, data in metrics.items():
            if isinstance(data, dict):
                lines.append(f"**{category}:**")
                for key, value in data.items():
                    if isinstance(value, (int, float)):
                        lines.append(
                            f"  - {key}: {value:.3f}"
                            if isinstance(value, float)
                            else f"  - {key}: {value}"
                        )
                    elif isinstance(value, list) and len(value) <= 5:
                        lines.append(f"  - {key}: {value}")
                    else:
                        lines.append(f"  - {key}: {type(value).__name__}")
        return "\n".join(lines)

    def _generate_fallback_narrative(self, metrics: Dict, anomalies: List[Dict]) -> str:
        """Fallback narrative when LLM unavailable"""
        lines = [
            f"# Flight Analysis Report (Fallback Mode)",
            f"**Summary**: {metrics.get('summary', 'No summary available')}",
            "",
            "## Anomalies Detected",
        ]

        if anomalies:
            for a in anomalies:
                lines.append(f"- **{a['severity'].upper()}**: {a['message']}")
        else:
            lines.append("No anomalies detected.")

        lines.extend(
            [
                "",
                "## Key Metrics",
                self._metrics_to_text(metrics),
                "",
                "## Recommendations",
                "- Review EKF2 innovation thresholds if violation rate > 5%",
                "- Monitor VIO drift; recalibrate if > 5 cm/s",
                "- Verify Silvus link quality; investigate if packet loss > 10%",
                "- Monitor battery voltage sag; replace if sag > 1.0V",
            ]
        )

        return "\n".join(lines)

    def _generate_recommendations(
        self, metrics: Dict, anomalies: List[Dict]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # EKF2 recommendations
        ekf = metrics.get("ekf2_health", {})
        if ekf.get("pos_3sigma_violation_rate", 0) > 0.05:
            recommendations.append(
                f"INCREASE EKF2_EV_DELAY from current to {int(metrics.get('ekf2_ev_delay', 10) + 5)}ms "
                f"(current violation rate: {ekf['pos_3sigma_violation_rate']*100:.1f}%)"
            )

        # VIO recommendations
        vio = metrics.get("vio_quality", {})
        if vio.get("avg_drift_rate_m_s", 0) > 0.05:
            recommendations.append(
                f"RECALIBRATE VIO: drift rate {vio['avg_drift_rate_m_s']*100:.1f} cm/s > 5 cm/s threshold. "
                f"Check camera calibration, lighting, and texture."
            )

        # GPS recommendations
        gps = metrics.get("gps_quality", {})
        if gps.get("avg_horizontal_accuracy", 999) > 5.0:
            recommendations.append(
                f"IMPROVE GPS ACCURACY: current {gps['avg_horizontal_accuracy']:.1f}m > 5m threshold. "
                f"Check fake GPS origin, VIO covariance, and EKF2_GPS_P_NOISE."
            )

        # Silvus recommendations
        silvus = metrics.get("silvus_link", {})
        if silvus.get("avg_packet_loss_pct", 0) > 10:
            recommendations.append(
                f"INVESTIGATE SILVUS LINK: {silvus['avg_packet_loss_pct']:.1f}% packet loss > 10% threshold. "
                f"Check antenna alignment, frequency, and transmit power."
            )

        # Battery recommendations
        battery = metrics.get("battery_health", {})
        if battery.get("voltage_sag_v", 0) > 1.0:
            recommendations.append(
                f"REPLACE BATTERY: voltage sag {battery['voltage_sag_v']:.2f}V > 1.0V threshold. "
                f"Min voltage: {battery['min_voltage_v']:.2f}V."
            )

        # Anomaly-based recommendations
        for anomaly in anomalies:
            if (
                anomaly["type"] == "ekf2_innovation_excess"
                and anomaly["severity"] == "high"
            ):
                recommendations.append(
                    "URGENT: EKF2 innovation excessive. Ground aircraft immediately. "
                    "Check VIO alignment, EKF2_EV_DELAY, and sensor health."
                )
            elif (
                anomaly["type"] == "silvus_high_loss" and anomaly["severity"] == "high"
            ):
                recommendations.append(
                    "HIGH PRIORITY: Silvus link degraded. Switch to manual/RTL mode if operating beyond VLOS."
                )

        return (
            recommendations
            if recommendations
            else ["No specific recommendations - all systems nominal"]
        )


def analyze_flight_log(
    db_path: str,
    flight_id: str,
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o",
) -> FlightAnalysisResult:
    """Convenience function for flight analysis"""
    analyzer = LLMFlightAnalyzer(db_path, llm_provider, llm_model)
    return analyzer.analyze_flight(flight_id)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="LLM Flight Log Analyzer")
    parser.add_argument("flight_id", help="Flight ID to analyze")
    parser.add_argument(
        "--db",
        default="/Users/amaster/projectm/Q250-V3-Opti/flight_logs/db/flightlog.db",
        help="Database path",
    )
    parser.add_argument(
        "--provider", choices=["openai", "anthropic", "local"], default="openai"
    )
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--output", help="Output file (JSON)")

    args = parser.parse_args()

    result = analyze_flight_log(args.db, args.flight_id, args.provider, args.model)

    output = {
        "flight_id": result.flight_id,
        "summary": result.summary,
        "ekf2_health": result.ekf2_health,
        "vio_quality": result.vio_quality,
        "gps_quality": result.gps_quality,
        "avoidance_performance": result.avoidance_performance,
        "silvus_link": result.silvus_link,
        "battery_health": result.battery_health,
        "anomalies": result.anomalies,
        "recommendations": result.recommendations,
        "llm_narrative": result.llm_narrative,
        "timestamp": result.timestamp,
    }

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Report saved to {args.output}")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
