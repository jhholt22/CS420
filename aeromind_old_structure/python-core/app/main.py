from app.app_controller import AppController
from app.runtime_config import RuntimeConfig


def main():
    cfg = RuntimeConfig()
    print(f"[AeroMind] Run ID: {cfg.run_id}")
    mode = input("Mode? (sim/drone): ").strip().lower()
    use_drone = mode == "drone"

    controller = AppController(use_drone=use_drone, cfg=cfg)
    controller.run()


if __name__ == "__main__":
    main()
