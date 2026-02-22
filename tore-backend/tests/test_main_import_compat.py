import main


def test_main_compat_exports_present():
    assert hasattr(main, "app")
    assert hasattr(main, "validate_env_or_warn")
    assert hasattr(main, "run_migrations_on_startup")
