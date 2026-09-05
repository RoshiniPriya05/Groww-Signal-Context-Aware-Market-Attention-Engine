from app.services.ai_story_service import generate_change_story, numbers_are_grounded


def test_change_story_uses_only_payload_numbers() -> None:
    payload = {
        "symbol": "RELIANCE",
        "price": 2744.8,
        "previous_price": 2920.0,
        "price_delta": -175.2,
        "price_delta_pct": -6.0,
        "volume": 728,
        "previous_volume": 260,
        "volume_delta_pct": 180.0,
        "z_volume": 8.0,
        "z_price": -8.0,
        "sector_relative_delta": -0.055,
        "mci": 90.12,
        "priority": "CRITICAL",
    }
    story = generate_change_story(payload)
    assert numbers_are_grounded(
        {k: v for k, v in story.items() if k != "grounding"},
        payload,
    )
    assert story["headline"]
    assert isinstance(story["what_changed_summary"], list)
    assert story["grounding"]["numbers_from_payload_only"] is True
