from __future__ import annotations

from universal_android_repair.ui.main_window import create_app


def main() -> None:
    app = create_app()
    app.exec()


if __name__ == "__main__":
    main()
