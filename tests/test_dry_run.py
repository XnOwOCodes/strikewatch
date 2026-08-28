from strikewatch.dry_run import main


def test_dry_run_sequence(capsys):
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert "QUIET → ALERT → QUIET" in captured.out
