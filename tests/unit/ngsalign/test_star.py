from copy import deepcopy

import pytest
import mock

from bcbio.ngsalign import star
from bcbio.pipeline import datadict as dd
from tests.unit.data import DATA as _DATA
from tests.unit.data import NAMES as _NAMES


@pytest.fixture
def data():
    return deepcopy(_DATA)


@pytest.fixture
def names():
    return deepcopy(_NAMES)


def test_get_star_dirnames(data, names):
    from bcbio.ngsalign.star import _get_star_dirnames
    align_dir = '/path/to/align/dir'
    lane = dd.get_lane(data)
    result = star._get_star_dirnames(align_dir, data, names)
    assert result.out_dir == '/path/to/align/dir/%s_star' % lane
    assert result.out_prefix == '/path/to/align/dir/%s' % lane
    assert result.out_file == '/path/to/align/dir/%sAligned.out.sam' % lane
    assert result.final_out == '/path/to/align/dir/%s_star/%s.bam' % (
        lane, names['sample'])


@pytest.yield_fixture
def mock_should_run(mocker):
    yield mocker.patch(
        'bcbio.ngsalign.star.config_utils.should_run_fusion')


def test_should_run_fusion(mock_should_run):
    config = mock.MagicMock()
    result = star._should_run_fusion(config)
    mock_should_run.assert_called_once_with('star', config)
    assert result == mock_should_run.return_value
