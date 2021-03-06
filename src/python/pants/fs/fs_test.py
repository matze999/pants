# Copyright 2019 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from dataclasses import dataclass
from pathlib import Path

from pants.engine.console import Console
from pants.engine.fs import CreateDigest, Digest, FileContent, Snapshot, Workspace
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.rules import Get, goal_rule, rule
from pants.fs.fs import is_child_of
from pants.testutil.test_base import TestBase


class WorkspaceGoalSubsystem(GoalSubsystem):
    name = "workspace-goal"


class WorkspaceGoal(Goal):
    subsystem_cls = WorkspaceGoalSubsystem


@dataclass(frozen=True)
class DigestRequest:
    create_digest: CreateDigest


@rule
def digest_request_singleton() -> DigestRequest:
    fc = FileContent(path="a.txt", content=b"hello")
    return DigestRequest(CreateDigest([fc]))


@goal_rule
async def workspace_goal_rule(
    console: Console, workspace: Workspace, digest_request: DigestRequest
) -> WorkspaceGoal:
    snapshot = await Get(Snapshot, CreateDigest, digest_request.create_digest)
    workspace.write_digest(snapshot.digest)
    console.print_stdout(snapshot.files[0], end="")
    return WorkspaceGoal(exit_code=0)


class WorkspaceInGoalRuleTest(TestBase):
    """This test is meant to ensure that the Workspace type successfully invokes the rust FFI
    function to write to disk in the context of a @goal_rule, without crashing or otherwise
    failing."""

    @classmethod
    def rules(cls):
        return (*super().rules(), workspace_goal_rule, digest_request_singleton)

    def test_goal(self) -> None:
        result = self.run_goal_rule(WorkspaceGoal)
        assert result.exit_code == 0
        assert result.stdout == "a.txt"
        assert Path(self.build_root, "a.txt").read_text() == "hello"


class WorkspaceTest(TestBase):
    def test_write_digest(self):
        # TODO(#8336): at some point, this test should require that Workspace only be invoked from
        #  an @goal_rule
        workspace = Workspace(self.scheduler)
        digest = self.request_product(
            Digest,
            [
                CreateDigest(
                    [FileContent("a.txt", b"hello"), FileContent("subdir/b.txt", b"goodbye")]
                )
            ],
        )

        path1 = Path(self.build_root, "a.txt")
        path2 = Path(self.build_root, "subdir/b.txt")
        assert not path1.is_file()
        assert not path2.is_file()

        workspace.write_digest(digest)
        assert path1.is_file()
        assert path2.is_file()

        workspace.write_digest(digest, path_prefix="prefix")
        assert Path(self.build_root, "prefix", path1).is_file()
        assert Path(self.build_root, "prefix", path2).is_file()


def test_is_child_of() -> None:
    mock_build_root = Path("/mock/build/root")

    assert is_child_of(Path("/mock/build/root/dist/dir"), mock_build_root)
    assert is_child_of(Path("dist/dir"), mock_build_root)
    assert is_child_of(Path("./dist/dir"), mock_build_root)
    assert is_child_of(Path("../root/dist/dir"), mock_build_root)
    assert is_child_of(Path(""), mock_build_root)
    assert is_child_of(Path("./"), mock_build_root)

    assert not is_child_of(Path("/other/random/directory/root/dist/dir"), mock_build_root)
    assert not is_child_of(Path("../not_root/dist/dir"), mock_build_root)
