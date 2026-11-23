"""
Main entry point for training pipelines
"""

import sys
import argparse
from pathlib import Path

# Add pipeline to path
sys.path.insert(0, str(Path(__file__).parent))


def run_intrusion_detection():
    from pipelines.intrusion_detection import main

    return main()


def run_attack_classification():
    from pipelines.attack_classification import main

    return main()


def run_audio_enhancement():
    print("Audio enhancement pipeline not yet implemented")
    # from pipelines.audio_enhancement import main
    # return main()


def run_protocol_anomaly():
    print("Protocol anomaly pipeline not yet implemented")
    # from pipelines.protocol_anomaly import main
    # return main()


def run_routing_optimization():
    print("Routing optimization pipeline not yet implemented")
    # from pipelines.routing_optimization import main
    # return main()


PIPELINES = {
    "intrusion_detection": run_intrusion_detection,
    "attack_classification": run_attack_classification,
    "audio_enhancement": run_audio_enhancement,
    "protocol_anomaly": run_protocol_anomaly,
    "routing_optimization": run_routing_optimization,
}


def main():
    parser = argparse.ArgumentParser(description="Training Pipeline Runner")
    parser.add_argument(
        "pipeline", choices=list(PIPELINES.keys()), help="Pipeline to run"
    )
    parser.add_argument("--config", type=str, help="Config file path")

    args = parser.parse_args()

    print(f"Running pipeline: {args.pipeline}")
    PIPELINES[args.pipeline]()


if __name__ == "__main__":
    main()
