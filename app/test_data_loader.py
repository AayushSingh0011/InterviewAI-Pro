from app.services.data_loader import load_candidates, load_curriculum


def test_load_candidates():
    candidates = load_candidates()

    assert candidates is not None
    assert isinstance(candidates, list)


def test_load_curriculum():
    curriculum = load_curriculum()

    assert curriculum is not None
    assert isinstance(curriculum, list)