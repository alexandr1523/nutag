from scripts.check_database_url import is_admin_like_database_user


def test_admin_like_database_user_detects_owner_and_admin_names() -> None:
    assert is_admin_like_database_user("neondb_owner")
    assert is_admin_like_database_user("postgres")
    assert is_admin_like_database_user("nutag_admin")


def test_admin_like_database_user_allows_regular_app_names() -> None:
    assert not is_admin_like_database_user("nutag_app")
    assert not is_admin_like_database_user("nutag_runtime")
    assert not is_admin_like_database_user(None)
