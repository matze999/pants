# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import sys
import unittest.mock

from pants.engine.internals.native import Native
from pants.pantsd.pants_daemon import PantsDaemon, _LoggerStream
from pants.pantsd.pants_daemon_core import PantsDaemonCore
from pants.pantsd.service.pants_service import PantsServices
from pants.util.contextutil import stdio_as

PATCH_OPTS = dict(autospec=True, spec_set=True)


TEST_LOG_LEVEL = logging.INFO


def test_logger_stream_write():
    mock_logger = unittest.mock.Mock()
    _LoggerStream(mock_logger, TEST_LOG_LEVEL, None).write("testing 1 2 3")
    mock_logger.log.assert_called_once_with(TEST_LOG_LEVEL, "testing 1 2 3")


def test_logger_stream_write_multiline():
    mock_logger = unittest.mock.Mock()
    _LoggerStream(mock_logger, TEST_LOG_LEVEL, None).write("testing\n1\n2\n3\n\n")
    mock_logger.log.assert_has_calls(
        [
            unittest.mock.call(TEST_LOG_LEVEL, "testing"),
            unittest.mock.call(TEST_LOG_LEVEL, "1"),
            unittest.mock.call(TEST_LOG_LEVEL, "2"),
            unittest.mock.call(TEST_LOG_LEVEL, "3"),
        ]
    )


def test_logger_stream_flush():
    _LoggerStream(unittest.mock.Mock(), TEST_LOG_LEVEL, None).flush()


@unittest.mock.patch("os.close", **PATCH_OPTS)
def test_close_stdio(mock_close):
    mock_options = unittest.mock.Mock()
    mock_options_values = unittest.mock.Mock()
    mock_options.for_global_scope.return_value = mock_options_values
    mock_options_values.pants_subprocessdir = "non_existent_dir"
    mock_server = unittest.mock.Mock()

    def create_services(bootstrap_options, legacy_graph_scheduler):
        return PantsServices()

    pantsd = PantsDaemon(
        native=Native(),
        work_dir="test_work_dir",
        log_level=logging.INFO,
        server=mock_server,
        core=PantsDaemonCore(create_services),
        metadata_base_dir="/tmp/pants_test_metadata_dir",
        bootstrap_options=mock_options,
    )

    with stdio_as(-1, -1, -1):
        handles = (sys.stdin, sys.stdout, sys.stderr)
        fds = [h.fileno() for h in handles]
        pantsd._close_stdio()
        mock_close.assert_has_calls(unittest.mock.call(x) for x in fds)
        for handle in handles:
            assert handle.closed is True
