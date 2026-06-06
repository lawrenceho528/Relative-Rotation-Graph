import runpy
import pathlib


if __name__ == "__main__":
    runpy.run_path(str(pathlib.Path(__file__).with_name("rrg-formula-audit.py")), run_name="__main__")
