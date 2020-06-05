from pathlib import Path
import sys

# add root dir to sys.path to enable import from parent directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from project3 import Proxy


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <port>")
        return
    with Proxy(port=int(sys.argv[1])) as proxy:
        proxy.run()


if __name__ == '__main__':
    main()
