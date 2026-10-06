"""Package the cloud handlers and shared modules for AWS Lambda."""

import argparse
from pathlib import Path
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLOUD_ROOT = PROJECT_ROOT / "cloud"


def package(output_path):
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(CLOUD_ROOT.rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            archive.write(source, source.relative_to(PROJECT_ROOT).as_posix())
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "dist" / "cloudcrowd-lambda.zip"),
        help="destination ZIP path",
    )
    args = parser.parse_args()
    output_path = package(args.output)
    print(f"Lambda package created: {output_path}")


if __name__ == "__main__":
    main()
