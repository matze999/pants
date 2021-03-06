# Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass

import pytest

from pants.core.util_rules.filter_empty_sources import (
    FieldSetsWithSources,
    FieldSetsWithSourcesRequest,
    TargetsWithSources,
    TargetsWithSourcesRequest,
)
from pants.core.util_rules.filter_empty_sources import rules as filter_empty_sources_rules
from pants.engine.addresses import Address
from pants.engine.rules import QueryRule
from pants.engine.target import FieldSet, Sources, Tags, Target
from pants.option.options_bootstrapper import OptionsBootstrapper
from pants.testutil.option_util import create_options_bootstrapper
from pants.testutil.rule_runner import RuleRunner


@pytest.fixture
def rule_runner() -> RuleRunner:
    return RuleRunner(
        rules=[
            *filter_empty_sources_rules(),
            QueryRule(FieldSetsWithSources, (FieldSetsWithSourcesRequest, OptionsBootstrapper)),
            QueryRule(TargetsWithSources, (TargetsWithSourcesRequest, OptionsBootstrapper)),
        ]
    )


def test_filter_field_sets(rule_runner: RuleRunner) -> None:
    @dataclass(frozen=True)
    class MockFieldSet(FieldSet):
        sources: Sources
        # Another field to demo that we will preserve the whole FieldSet data structure.
        tags: Tags

    rule_runner.create_file("f1.txt")
    valid_addr = Address("", target_name="valid")
    valid_field_set = MockFieldSet(
        valid_addr, Sources(["f1.txt"], address=valid_addr), Tags(None, address=valid_addr)
    )

    empty_addr = Address("", target_name="empty")
    empty_field_set = MockFieldSet(
        empty_addr, Sources(None, address=empty_addr), Tags(None, address=empty_addr)
    )

    result = rule_runner.request_product(
        FieldSetsWithSources,
        [
            FieldSetsWithSourcesRequest([valid_field_set, empty_field_set]),
            create_options_bootstrapper(),
        ],
    )
    assert tuple(result) == (valid_field_set,)


def test_filter_targets(rule_runner: RuleRunner) -> None:
    class MockTarget(Target):
        alias = "target"
        core_fields = (Sources,)

    class MockTargetWithNoSourcesField(Target):
        alias = "no_sources"
        core_fields = ()

    rule_runner.create_file("f1.txt")
    valid_tgt = MockTarget({Sources.alias: ["f1.txt"]}, address=Address("", target_name="valid"))
    empty_tgt = MockTarget({}, address=Address("", target_name="empty"))
    invalid_tgt = MockTargetWithNoSourcesField({}, address=Address("", target_name="invalid"))

    result = rule_runner.request_product(
        TargetsWithSources,
        [
            TargetsWithSourcesRequest([valid_tgt, empty_tgt, invalid_tgt]),
            create_options_bootstrapper(),
        ],
    )
    assert tuple(result) == (valid_tgt,)
