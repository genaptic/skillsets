"""Illustrative exception hierarchy; adapt names and caller contracts."""


class ExampleError(Exception):
    """Base class for expected, public package failures."""


class ConfigurationError(ExampleError):
    """The supplied configuration is invalid or incomplete."""


class ResourceNotFoundError(ExampleError):
    """A requested domain resource does not exist."""


class DependencyUnavailableError(ExampleError):
    """A required dependency is temporarily unavailable."""


def load_record(repository, record_id: str):
    try:
        return repository.fetch(record_id)
    except repository.NotFound as exc:
        raise ResourceNotFoundError(f"record {record_id!r} was not found") from exc
