# Copyright 2020 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from typing import List, Optional, Sequence, Tuple

from pants.backend.python.lint.docformatter.rules import DocformatterFieldSet, DocformatterRequest
from pants.backend.python.lint.docformatter.rules import rules as docformatter_rules
from pants.backend.python.target_types import PythonLibrary
from pants.core.goals.fmt import FmtResult
from pants.core.goals.lint import LintResult, LintResults
from pants.core.util_rules.source_files import SourceFiles, SourceFilesRequest
from pants.engine.addresses import Address
from pants.engine.fs import CreateDigest, Digest, FileContent
from pants.engine.rules import QueryRule
from pants.engine.target import Target
from pants.option.options_bootstrapper import OptionsBootstrapper
from pants.testutil.external_tool_test_base import ExternalToolTestBase
from pants.testutil.option_util import create_options_bootstrapper


class DocformatterIntegrationTest(ExternalToolTestBase):

    good_source = FileContent(path="good.py", content=b'"""Good docstring."""\n')
    bad_source = FileContent(path="bad.py", content=b'"""Oops, missing a period"""\n')
    fixed_bad_source = FileContent(path="bad.py", content=b'"""Oops, missing a period."""\n')

    @classmethod
    def rules(cls):
        return (
            *super().rules(),
            *docformatter_rules(),
            QueryRule(LintResults, (DocformatterRequest, OptionsBootstrapper)),
            QueryRule(FmtResult, (DocformatterRequest, OptionsBootstrapper)),
            QueryRule(SourceFiles, (SourceFilesRequest, OptionsBootstrapper)),
        )

    def make_target(self, source_files: List[FileContent]) -> Target:
        for source_file in source_files:
            self.create_file(f"{source_file.path}", source_file.content.decode())
        return PythonLibrary({}, address=Address.parse(":target"))

    def run_docformatter(
        self, targets: List[Target], *, passthrough_args: Optional[str] = None, skip: bool = False
    ) -> Tuple[Sequence[LintResult], FmtResult]:
        args = ["--backend-packages=pants.backend.python.lint.docformatter"]
        if passthrough_args:
            args.append(f"--docformatter-args='{passthrough_args}'")
        if skip:
            args.append("--docformatter-skip")
        options_bootstrapper = create_options_bootstrapper(args=args)
        field_sets = [DocformatterFieldSet.create(tgt) for tgt in targets]
        lint_results = self.request_product(
            LintResults, [DocformatterRequest(field_sets), options_bootstrapper]
        )
        input_sources = self.request_product(
            SourceFiles,
            [
                SourceFilesRequest(field_set.sources for field_set in field_sets),
                options_bootstrapper,
            ],
        )
        fmt_result = self.request_product(
            FmtResult,
            [
                DocformatterRequest(field_sets, prior_formatter_result=input_sources.snapshot),
                options_bootstrapper,
            ],
        )
        return lint_results.results, fmt_result

    def get_digest(self, source_files: List[FileContent]) -> Digest:
        return self.request_product(Digest, [CreateDigest(source_files)])

    def test_passing_source(self) -> None:
        target = self.make_target([self.good_source])
        lint_results, fmt_result = self.run_docformatter([target])
        assert len(lint_results) == 1
        assert lint_results[0].exit_code == 0
        assert lint_results[0].stderr == ""
        assert fmt_result.output == self.get_digest([self.good_source])
        assert fmt_result.did_change is False

    def test_failing_source(self) -> None:
        target = self.make_target([self.bad_source])
        lint_results, fmt_result = self.run_docformatter([target])
        assert len(lint_results) == 1
        assert lint_results[0].exit_code == 3
        assert lint_results[0].stderr.strip() == self.bad_source.path
        assert fmt_result.output == self.get_digest([self.fixed_bad_source])
        assert fmt_result.did_change is True

    def test_mixed_sources(self) -> None:
        target = self.make_target([self.good_source, self.bad_source])
        lint_results, fmt_result = self.run_docformatter([target])
        assert len(lint_results) == 1
        assert lint_results[0].exit_code == 3
        assert lint_results[0].stderr.strip() == self.bad_source.path
        assert fmt_result.output == self.get_digest([self.good_source, self.fixed_bad_source])
        assert fmt_result.did_change is True

    def test_multiple_targets(self) -> None:
        targets = [
            self.make_target([self.good_source]),
            self.make_target([self.bad_source]),
        ]
        lint_results, fmt_result = self.run_docformatter(targets)
        assert len(lint_results) == 1
        assert lint_results[0].exit_code == 3
        assert lint_results[0].stderr.strip() == self.bad_source.path
        assert fmt_result.output == self.get_digest([self.good_source, self.fixed_bad_source])
        assert fmt_result.did_change is True

    def test_respects_passthrough_args(self) -> None:
        needs_config = FileContent(
            path="needs_config.py",
            content=b'"""\nOne line docstring acting like it\'s multiline.\n"""\n',
        )
        target = self.make_target([needs_config])
        lint_results, fmt_result = self.run_docformatter(
            [target], passthrough_args="--make-summary-multi-line"
        )
        assert len(lint_results) == 1
        assert lint_results[0].exit_code == 0
        assert lint_results[0].stderr == ""
        assert fmt_result.output == self.get_digest([needs_config])
        assert fmt_result.did_change is False

    def test_skip(self) -> None:
        target = self.make_target([self.bad_source])
        lint_results, fmt_result = self.run_docformatter([target], skip=True)
        assert not lint_results
        assert fmt_result.skipped is True
        assert fmt_result.did_change is False
