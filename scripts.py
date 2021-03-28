from subprocess import CalledProcessError, run
import sys


def test(args):
    try:
        run(["flake8"], check=True)
        run(
            ["pytest", "--cov=observ", "--cov-report=term-missing"] + args, check=True,
        )
    except CalledProcessError:
        sys.exit(1)


def main():
    cmd = sys.argv[0]
    if cmd == "test":
        test(sys.argv[1:])
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
