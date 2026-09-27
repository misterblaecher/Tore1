from app.services.code_service import random_code
from app.services.event_feature_service import default_event_config_payload
from app.services.organization_compat_service import ORGA_ROLE_RANK


def test_random_code_keeps_historical_shape():
    code = random_code(12)
    assert len(code) == 12
    assert code.isalnum()
    assert code == code.upper()


def test_event_config_defaults_match_legacy_contract():
    assert default_event_config_payload() == {
        "menu_enabled": True,
        "wallet_enabled": True,
        "entry_enabled": False,
        "checkin_enabled": False,
        "battles_enabled": False,
        "hunt_enabled": False,
        "report_enabled": True,
        "allow_user_bets": False,
    }


def test_organization_role_ranks_keep_legacy_order():
    assert ORGA_ROLE_RANK["FOLLOWER"] < ORGA_ROLE_RANK["MEMBER"]
    assert ORGA_ROLE_RANK["MEMBER"] < ORGA_ROLE_RANK["STAFF"]
    assert ORGA_ROLE_RANK["STAFF"] < ORGA_ROLE_RANK["BUREAU"]
    assert ORGA_ROLE_RANK["BUREAU"] < ORGA_ROLE_RANK["PRESIDENT"]
    assert ORGA_ROLE_RANK["PRESIDENT"] < ORGA_ROLE_RANK["OWNER"]
