"""Compatible local gate entrypoint for the production operator seed utility."""

from backend.app.operations.demo_seed import digest as digest
from backend.app.operations.demo_seed import main
from backend.app.operations.demo_seed import source as source
from backend.app.operations.demo_seed import verify as verify

if __name__ == "__main__":
    main()
