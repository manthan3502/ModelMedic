from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class DuplicateActiveJob(Exception):
    pass


class OwnershipLost(Exception):
    pass
