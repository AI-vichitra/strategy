"""Tests for Step 5 (backend wiring): the public GET /api/pptx-templates
catalog route, and the ?template_id= query param on
GET /{report_id}/export/pptx. Run with:
cd backend && python -m pytest tests/test_pptx_templates_route.py -v

The export-route tests call `export_report_pptx` directly as a plain async
function (not through TestClient/a real DB) — this project's existing
report.id/user.id checks go through SQLAlchemy against the real
backend/stratai.db, and these tests have no business touching that file.
`report_service.get_report` is monkeypatched to return a fake report, and a
tiny `_FakeDB` stands in for the AsyncSession (its one `.execute()` call,
the brand/brand_kit lookup in `_build_pptx_response`, just needs `.first()`
to return None so brand_name/brand_kit both default). The real
`generate_pptx`/`get_template` still run underneath, so these are true
wiring tests, not mocks-all-the-way-down.
"""
import asyncio
import io
import os
import sys
from types import SimpleNamespace
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.util import Pt

from backend.main import app
from backend.routers import reports as reports_router
from backend.services import report_service as report_service_module
import backend.services.pptx_service as pptx_service_module
from backend.services.template_service import DEFAULT_TEMPLATE, TemplateSpec


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/pptx-templates
# ─────────────────────────────────────────────────────────────────────────────
def test_list_pptx_templates_returns_200_no_auth():
    """The picker shows only the 4 kept templates — "default" stays the code
    fallback for an unset/invalid template_id (see get_template), but is
    disabled in the registry so it's hidden from this public catalog."""
    client = TestClient(app)
    resp = client.get("/api/pptx-templates")
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, list)
    by_id = {t["id"]: t for t in body}
    assert set(by_id) == {"executive", "bold", "corporate-blue", "midnight-tech"}
    assert "default" not in by_id
    assert by_id["executive"]["name"] == "Executive"


def test_list_pptx_templates_dto_never_leaks_the_full_spec():
    client = TestClient(app)
    body = client.get("/api/pptx-templates").json()
    assert body  # at least the 4 kept templates must be present

    leaked_keys = {"fonts", "type_scale", "palette", "backgrounds", "geometry", "fit", "slots", "art", "enabled"}
    for entry in body:
        assert set(entry.keys()) <= {"id", "name", "description", "preview"}
        assert not (set(entry.keys()) & leaked_keys)


# ─────────────────────────────────────────────────────────────────────────────
# GET /{report_id}/export/pptx?template_id=...
# ─────────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def first(self):
        return None


class _FakeDB:
    async def execute(self, *args, **kwargs):
        return _FakeResult()


def _fake_report():
    return SimpleNamespace(
        id="report-1",
        project_id="project-1",
        user_id="user-1",
        agent_type="default",
        title="Test Report",
        content="### Section\nSome text.",
        extracted_palette=None,
    )


async def _fake_get_report(db, report_id, user_id):
    return _fake_report()


def _fake_current_user():
    return SimpleNamespace(id="user-1")


def test_export_pptx_with_no_template_id_calls_get_template_with_none(monkeypatch):
    monkeypatch.setattr(report_service_module, "get_report", _fake_get_report)

    captured = []
    real_get_template = pptx_service_module.get_template

    def spy_get_template(template_id: Optional[str]):
        captured.append(template_id)
        return real_get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", spy_get_template)

    resp = _run(reports_router.export_report_pptx(
        "report-1", template_id=None, db=_FakeDB(), current_user=_fake_current_user(),
    ))

    assert captured == [None]
    assert resp.body[:2] == b"PK"


def test_export_pptx_with_alt_template_id_threads_through_and_renders(monkeypatch):
    monkeypatch.setattr(report_service_module, "get_report", _fake_get_report)

    # A distinctive alt TemplateSpec (same shape as DEFAULT_TEMPLATE, but a
    # bumped cover-title size) so the rendered deck can prove it was actually
    # used, not just that the id was accepted.
    alt_tpl = TemplateSpec(
        id="alt-template",
        name="Alt",
        fonts=DEFAULT_TEMPLATE.fonts,
        type_scale={**DEFAULT_TEMPLATE.type_scale, "cover_title": 50},
        palette=None,
        backgrounds=DEFAULT_TEMPLATE.backgrounds,
        geometry=DEFAULT_TEMPLATE.geometry,
        fit=DEFAULT_TEMPLATE.fit,
        slots=DEFAULT_TEMPLATE.slots,
        art=DEFAULT_TEMPLATE.art,
    )

    captured_template_ids = []
    real_get_template = pptx_service_module.get_template

    def spy_get_template(template_id: Optional[str]):
        captured_template_ids.append(template_id)
        if template_id == "alt-template":
            return alt_tpl
        return real_get_template(template_id)

    monkeypatch.setattr(pptx_service_module, "get_template", spy_get_template)

    captured_report_data = {}
    real_generate_pptx = pptx_service_module.generate_pptx

    async def spy_generate_pptx(report_data):
        captured_report_data.update(report_data)
        return await real_generate_pptx(report_data)

    monkeypatch.setattr(pptx_service_module, "generate_pptx", spy_generate_pptx)

    resp = _run(reports_router.export_report_pptx(
        "report-1", template_id="alt-template", db=_FakeDB(), current_user=_fake_current_user(),
    ))

    # report_data carried the query param through, and get_template actually
    # received it.
    assert captured_report_data.get("template_id") == "alt-template"
    assert "alt-template" in captured_template_ids

    # The deck itself reflects the alt template, not just the default.
    prs = Presentation(io.BytesIO(resp.body))
    cover = prs.slides[0]
    found_resized_title = False
    for shape in cover.shapes:
        if not shape.has_text_frame:
            continue
        for p in shape.text_frame.paragraphs:
            for run in p.runs:
                if run.text == "Test Report" and run.font.size == Pt(50):
                    found_resized_title = True
    assert found_resized_title, "expected the cover title to render at the alt template's 50pt size"


def test_export_pptx_with_garbage_template_id_falls_back_without_500(monkeypatch):
    monkeypatch.setattr(report_service_module, "get_report", _fake_get_report)

    resp = _run(reports_router.export_report_pptx(
        "report-1", template_id="this-template-does-not-exist", db=_FakeDB(), current_user=_fake_current_user(),
    ))

    assert resp.status_code == 200
    assert resp.body[:2] == b"PK"
