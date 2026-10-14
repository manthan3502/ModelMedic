"""Production operator private S3 probe, using a new synthetic disposable prefix."""

from uuid import uuid4

from backend.app.core.config import Settings
from backend.app.storage.factory import artifact_store


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    if settings.artifact_backend != "s3" or settings.deployment_mode != "full":
        raise RuntimeError("Probe requires private S3 and isolated Full Mode operator access")
    store = artifact_store(settings)
    prefix = f"compatibility/{uuid4()}"
    key = prefix + "/synthetic.bin"
    try:
        store.put(key, b"synthetic compatibility fixture")
        assert store.exists(key)
        assert store.get(key) == b"synthetic compatibility fixture"
        try:
            store.put(key, b"must not replace")
        except OSError:
            pass
        else:
            raise RuntimeError("Provider does not enforce conditional write-once publication")
        assert store.get(key) == b"synthetic compatibility fixture"
    finally:
        store.delete_prefix(prefix)
    assert not store.exists(key)
    print("PASS: private object read/write/hash bytes, overwrite rejection and scoped cleanup")


if __name__ == "__main__":
    main()
