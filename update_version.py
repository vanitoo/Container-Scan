# update_version.py
import re
from pathlib import Path


def increment_version(version):
    """Увеличивает версию по семантическому версионированию"""
    parts = version.split('.')
    if len(parts) == 3:
        major, minor, patch = parts
        patch = int(patch) + 1

        if patch >= 10:  # Если patch достигает 10, увеличиваем minor
            patch = 0
            minor = int(minor) + 1
            if minor >= 10:  # Если minor достигает 10, увеличиваем major
                minor = 0
                major = int(major) + 1

        return f"{major}.{minor}.{patch}"
    return version


def update_version_file():
    version_file = Path("version.py")
    content = version_file.read_text(encoding="utf-8")

    # Ищем текущую версию
    match = re.search(r'__version__ = "([\d.]+)"', content)
    if match:
        current_version = match.group(1)
        new_version = increment_version(current_version)

        # Заменяем версию
        new_content = re.sub(
            r'__version__ = "[\d.]+"',
            f'__version__ = "{new_version}"',
            content
        )

        version_file.write_text(new_content, encoding="utf-8")
        print(f"Updated version: {current_version} -> {new_version}")
        return new_version
    return None


if __name__ == "__main__":
    update_version_file()
