"""The bigger bound is an explicit contract, while legacy wire remains bounded."""

import pytest
from pydantic import ValidationError

from data.dq.full_contract import FullBinding, PortfolioBinding


def test_explicit_source_count_schemas_have_distinct_versions_and_bounds():
    old = FullBinding.model_json_schema()["properties"]
    new = PortfolioBinding.model_json_schema()["properties"]
    assert old["contract_version"]["const"] == "raw-dq-binding-2.0.0"
    assert new["contract_version"]["const"] == "raw-dq-binding-2.1.0"
    assert old["source_event_count"]["maximum"] == 4096
    assert new["source_event_count"]["maximum"] == 8192
    with pytest.raises(ValidationError):
        PortfolioBinding.model_validate({"contract_version": "raw-dq-binding-2.1.0", "source_event_count": 8193})
