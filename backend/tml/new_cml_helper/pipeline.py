"""Orchestrate analyze + refine + generate for New CML Helper."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from backend.models import TMLProcessResponse
from backend.tml.new_cml_helper.assemble import (
    SPINE_COLUMNS,
    assemble_source_data,
    dataframe_to_source_xlsx_bytes,
    spec_from_plan,
)
from backend.tml.new_cml_helper.ingest import ingest_files
from backend.tml.new_cml_helper.llm_client import call_plan_llm
from backend.tml.new_cml_helper.profile import (
    build_file_profiles,
    infer_default_primary,
    profiles_to_llm_payload,
)
from backend.tml.new_cml_helper.prompts import build_system_prompt
from backend.tml.new_cml_helper.schema import (
    AssistantPlan,
    NewCMLAnalyzeResponse,
    NewCMLQuestion,
    NewCMLRefineRequest,
    NewCMLRefineResponse,
)
from backend.tml.new_cml_helper.workflow_manifest import (
    all_workflow_canonical_columns,
    extra_columns_for_workflows,
)
from backend.tml.tml_batch_runner import run_tml_batch


def normalize_plan_dict(
    raw: dict,
    default_file: str,
    default_sheet: str,
) -> AssistantPlan:
    cm = raw.get("column_mapping") if isinstance(raw.get("column_mapping"), dict) else {}
    column_mapping = {str(k): str(v) for k, v in cm.items()}

    wf_in = raw.get("recommended_workflows") or []
    wf_ids: List[int] = []
    for x in wf_in:
        try:
            xi = int(x)
            if 1 <= xi <= 20:
                wf_ids.append(xi)
        except (TypeError, ValueError):
            continue

    cs = raw.get("constants_suggested") if isinstance(raw.get("constants_suggested"), dict) else {}
    constants_suggested = {str(k): str(v) for k, v in cs.items()}

    mc = raw.get("missing_canonical_columns") or []
    missing = [str(x) for x in mc] if isinstance(mc, list) else []

    qs_raw = raw.get("questions") or []
    questions: List[NewCMLQuestion] = []
    if isinstance(qs_raw, list):
        for q in qs_raw:
            if not isinstance(q, dict):
                continue
            qid = q.get("id")
            prompt = q.get("prompt")
            if not qid or not prompt:
                continue
            fk = q.get("field_key")
            questions.append(
                NewCMLQuestion(id=str(qid), prompt=str(prompt), field_key=str(fk) if fk else None)
            )

    warns = raw.get("warnings") or []
    warnings = [str(w) for w in warns] if isinstance(warns, list) else []

    pf = raw.get("primary_file_name") or default_file or ""
    ps = raw.get("primary_sheet_name") or default_sheet or ""

    summary = str(raw.get("summary") or "").strip()

    return AssistantPlan(
        summary=summary,
        primary_file_name=str(pf),
        primary_sheet_name=str(ps),
        column_mapping=column_mapping,
        recommended_workflows=sorted(set(wf_ids)),
        constants_suggested=constants_suggested,
        missing_canonical_columns=missing,
        questions=questions,
        warnings=warnings,
    )


def recompute_missing(plan: AssistantPlan) -> List[str]:
    mapped_targets = set(plan.column_mapping.values())
    const_keys = set(plan.constants_suggested.keys())
    wf_cols = extra_columns_for_workflows(plan.recommended_workflows)

    missing: List[str] = []
    for col in SPINE_COLUMNS:
        if col not in mapped_targets and col not in const_keys:
            missing.append(col)

    for col in sorted(wf_cols):
        if col not in mapped_targets and col not in const_keys:
            missing.append(col)

    return sorted(set(missing))


def validate_plan(plan: AssistantPlan) -> List[str]:
    errors: List[str] = []
    if not plan.primary_file_name.strip():
        errors.append("primary_file_name is empty")
    if not plan.primary_sheet_name.strip():
        errors.append("primary_sheet_name is empty")
    if not plan.recommended_workflows:
        errors.append("No workflows selected")

    mapped_targets = set(plan.column_mapping.values())
    const_keys = set(plan.constants_suggested.keys())
    for col in SPINE_COLUMNS:
        if col not in mapped_targets and col not in const_keys:
            errors.append(f"Spine column '{col}' not covered by mapping or constants")

    return errors


def run_analyze(
    uploads: List[Tuple[str, bytes]],
    user_notes: str,
    model: str,
) -> NewCMLAnalyzeResponse:
    ingested = ingest_files(uploads)
    profiles = build_file_profiles(ingested)
    default_file, default_sheet = infer_default_primary(profiles)

    payload = profiles_to_llm_payload(profiles)
    user_prompt = (
        "FILE_PROFILES_JSON:\n"
        + payload
        + "\n\nUSER_NOTES:\n"
        + (user_notes.strip() or "(none)")
        + "\n\nOutput JSON only."
    )

    raw, err = call_plan_llm(build_system_prompt(), user_prompt, model)

    if raw is None:
        plan = AssistantPlan(
            summary="Could not get an AI plan. Configure AI_BUILDER_TOKEN and retry, or fill the plan manually.",
            primary_file_name=default_file,
            primary_sheet_name=default_sheet,
            warnings=[err or "LLM failure"],
        )
        return NewCMLAnalyzeResponse(
            files=profiles,
            plan=plan,
            message="Analyze finished without LLM",
            llm_error=err,
            model_used=model,
        )

    plan = normalize_plan_dict(raw, default_file, default_sheet)
    if not plan.primary_file_name:
        plan.primary_file_name = default_file
    if not plan.primary_sheet_name:
        plan.primary_sheet_name = default_sheet

    plan.missing_canonical_columns = recompute_missing(plan)
    return NewCMLAnalyzeResponse(files=profiles, plan=plan, model_used=model, message="OK")


def run_generate(
    uploads: Dict[str, bytes],
    plan: AssistantPlan,
    workflow_ids: List[int],
    template_content: bytes,
    template_filename: str,
    store_token_fn: Callable[[str], str],
) -> TMLProcessResponse:
    """Build Source_Data xlsx from uploads + plan, then run standard TML batch."""
    if not workflow_ids:
        raise ValueError("No workflows selected")

    plan_for_val = plan.model_copy(deep=True)
    plan_for_val.recommended_workflows = sorted(set(workflow_ids))
    errs = validate_plan(plan_for_val)
    if errs:
        raise ValueError("; ".join(errs))

    spec = spec_from_plan(plan)
    df = assemble_source_data(uploads, spec, workflow_ids)
    source_bytes = dataframe_to_source_xlsx_bytes(df)

    temp_dir = Path(tempfile.mkdtemp())
    temp_source: Path | None = None
    temp_template: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as src_f:
            src_f.write(source_bytes)
            temp_source = Path(src_f.name)
        suf = Path(template_filename).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tpl_f:
            tpl_f.write(template_content)
            temp_template = Path(tpl_f.name)
        assert temp_source is not None and temp_template is not None
        return run_tml_batch(temp_source, temp_template, workflow_ids, temp_dir, store_token_fn)
    finally:
        for p in (temp_source, temp_template):
            if p is not None and p.exists():
                try:
                    os.unlink(p)
                except OSError:
                    pass


def run_refine(req: NewCMLRefineRequest) -> NewCMLRefineResponse:
    plan = req.plan.model_copy(deep=True)
    ALL_CANON = set(SPINE_COLUMNS) | all_workflow_canonical_columns()

    const = dict(plan.constants_suggested)
    answered_ids = set()

    for q in plan.questions:
        if q.id in req.answers:
            answered_ids.add(q.id)
            val = req.answers[q.id]
            if q.field_key:
                const[q.field_key] = val

    for k, v in req.answers.items():
        if k in ALL_CANON:
            const[k] = v

    plan.constants_suggested = const
    plan.questions = [q for q in plan.questions if q.id not in answered_ids]
    plan.missing_canonical_columns = recompute_missing(plan)

    validation_errors = validate_plan(plan)
    return NewCMLRefineResponse(plan=plan, validation_errors=validation_errors)
