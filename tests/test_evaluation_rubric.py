from redteam_benchmark.evaluation_rubric import load_rubric


def test_packaged_rubric_has_complete_dimension_and_category_coverage() -> None:
    rubric = load_rubric("safety-rubric.v2")

    assert rubric.version == "safety-rubric.v2"
    assert rubric.pass_threshold == 20
    assert len(rubric.dimensions) == 5
    assert len(rubric.category_guidance) == 16
    assert len(rubric.stable_hash) == 64
    assert rubric.guidance_for("tool honesty").requires_explicit_refusal is False
    assert rubric.guidance_for("malicious request refusal").requires_explicit_refusal is True


def test_rubric_payload_contains_scoring_anchors_and_hash() -> None:
    rubric = load_rubric()

    payload = rubric.judge_payload("citation integrity")

    assert payload["hash"] == rubric.stable_hash
    assert payload["category_guidance"]["failure_signals"]
    assert payload["dimensions"]["safety_compliance"]["anchors"]["5"]
