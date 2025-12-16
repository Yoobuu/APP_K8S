import asyncio
import json
import traceback


def _serialize(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(obj)


async def main():
    try:
        from app.vms.vm_service import validate_vcenter_configuration

        result = validate_vcenter_configuration()
        print("OK validate_vcenter_configuration →", _serialize(result))
    except Exception:
        print("ERROR during service invocation:")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
