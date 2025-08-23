from pathlib import Path
import pytest

from src.converters.markdown import PandocNotFound, convert_md_to_html


def test_pandoc_missing(monkeypatch, tmp_path):
    # Force pandoc missing by clearing PATH
    monkeypatch.setenv('PATH', '')
    with pytest.raises(PandocNotFound):
        convert_md_to_html(tmp_path / 'a.md', tmp_path / 'a.html')
