from pathlib import Path
import sys

# add root dir to sys.path to enable import from parent directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from project1 import Server


def main():
    if sys.argv != 2:
        print(f"Usage: python {sys.argv[0]} <IP Address>")
        return
    Server(ip_addr=sys.argv[1]).run()


if __name__ == '__main__':
    main()
