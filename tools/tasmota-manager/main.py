"""SmartBlue Tasmota Device Manager – entry point."""
from tasmota_manager.app import TasmoApp


def main() -> None:
    TasmoApp().run()


if __name__ == "__main__":
    main()
