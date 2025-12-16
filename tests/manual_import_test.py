import traceback


def main():
    try:
        import app.main  # noqa: F401
        print("import OK")
    except Exception:
        print("ERROR during import:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
