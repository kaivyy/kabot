def test_version_is_0_6_7():
    import os
    import sys

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, project_root)

    import kabot

    assert kabot.__version__ == "0.6.7"
