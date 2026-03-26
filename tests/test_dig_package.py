import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from backend.pipeline.dig_package import (
    extract_dig_ids,
    get_target_gw_chainage,
    match_features_by_dimensions,
    parse_ili_file,
    parse_mdl_file,
    populate_excavation_summary,
)
from backend.pipeline.dig_package_reader import (
    _build_joint_context,
    _find_header_row_after,
    _match_joint_source_name,
    _parse_joint_summary_matrix,
    _extract_sources_from_block_label,
    _reshape_joint_summary_dataframe,
    build_feature_map_from_dig_package,
    logger as dig_package_reader_logger,
    parse_dig_package_excel,
)
from backend.pipeline.feature_map_builder import parse_orientation_to_hours


def _workbook_bytes(workbook: Workbook) -> bytes:
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _add_named_range(workbook: Workbook, name: str, sheet_name: str, cell_ref: str) -> None:
    column = "".join(ch for ch in cell_ref if ch.isalpha())
    row = "".join(ch for ch in cell_ref if ch.isdigit())
    workbook.defined_names[name] = DefinedName(name, attr_text=f"'{sheet_name}'!${column}${row}")


def test_parse_mdl_file_detects_header_after_title_rows():
    workbook = Workbook()
    ws = workbook.active
    ws.title = "2025 Features&Dig Export"
    ws["A1"] = "Master Dig List"
    ws.append([])
    ws.append(["Dig ID", "Feature ID", "Start Assessment", "End Assessment", "Target Girth Weld", "Pipeline Name", "Length (mm)", "Width (mm)"])
    ws.append(["GW-100", "F-1", 12, 18, 3150, "Main Line", 25.4, 12.7])

    df, column_mapping = parse_mdl_file(_workbook_bytes(workbook))

    assert column_mapping["dig_id"] == "Dig ID"
    assert column_mapping["target_girth_weld"] == "Target Girth Weld"
    assert extract_dig_ids(df, column_mapping) == ["GW-100"]


def test_parse_ili_file_uses_shared_detection_for_rosen_anomalies_sheet():
    workbook = Workbook()
    workbook.active.title = "Cover"
    ws = workbook.create_sheet("Anomalies Listing 2025")
    ws["A1"] = "Rosen export"
    ws.append(["Feature ID", "Description", "Length (mm)", "Width (mm)", "Peak Depth", "Orientation (hh:mm)", "ILI Chainage (m)", "Joint No. or US GW No."])
    ws.append(["F-1", "Metal Loss", 25.4, 12.7, 42, "03:30", 1000.5, 3150])

    df, column_mapping, sheet_name = parse_ili_file(_workbook_bytes(workbook), "Rosen-MFLA")

    assert sheet_name == "Anomalies Listing 2025"
    assert column_mapping["feature_id"] == "Feature ID"
    assert column_mapping["distance"] == "ILI Chainage (m)"
    assert column_mapping["joint_number"] == "Joint No. or US GW No."
    assert len(df) == 1


def test_populate_excavation_summary_writes_to_named_range_sheet():
    workbook = Workbook()
    intro_ws = workbook.active
    intro_ws.title = "Intro"
    template_ws = workbook.create_sheet("Template")

    _add_named_range(workbook, "tmp_numExv_num", "Template", "B2")
    _add_named_range(workbook, "tmp_numExp_num", "Template", "B10")

    mdl_row = pd.Series(
        {
            "assessment_length_col": 30,
            "start_assessment_col": 10,
            "end_assessment_col": 20,
            "exposure_length_col": 25,
            "start_exposure_col": 11,
            "end_exposure_col": 21,
        }
    )
    mdl_col_map = {
        "assessment_length": "assessment_length_col",
        "start_assessment": "start_assessment_col",
        "end_assessment": "end_assessment_col",
        "exposure_length": "exposure_length_col",
        "start_exposure": "start_exposure_col",
        "end_exposure": "end_exposure_col",
    }

    populate_excavation_summary(workbook, mdl_row, mdl_col_map, excavation_num=7)

    assert template_ws["B2"].value == "Excavation #7"
    assert template_ws["B3"].value == 30
    assert template_ws["B4"].value == 10
    assert template_ws["B5"].value == 20
    assert intro_ws["B2"].value is None


def test_get_target_gw_chainage_matches_normalized_joint_values():
    mdl_row = pd.Series({"target_gw_col": "3150"})
    mdl_col_map = {"target_girth_weld": "target_gw_col"}
    ili_df = pd.DataFrame(
        {
            "Joint Number": [3150.0, 3160.0],
            "ILI Chainage (m)": [1000.5, 1012.0],
        }
    )
    ili_col_map = {"joint_number": "Joint Number", "distance": "ILI Chainage (m)"}

    chainage = get_target_gw_chainage(mdl_row, ili_df, mdl_col_map, ili_col_map)

    assert chainage == 1000.5


def test_match_features_by_dimensions_handles_mm_to_inch_conversion():
    ili_df = pd.DataFrame(
        {
            "Length (in)": [1.0, 2.0],
            "Width (in)": [0.5, 0.75],
        }
    )
    ili_col_map = {"length": "Length (in)", "width": "Width (in)"}

    matched = match_features_by_dimensions(25.4, 12.7, ili_df, ili_col_map)

    assert len(matched) == 1
    assert matched.index.tolist() == [0]


def test_parse_dig_package_excel_propagates_merged_joint_summary_labels():
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Dig Package"
    ws["A1"] = "Joint Summary"
    ws["A2"] = "Girth Weld No."
    ws["B2"] = 4570
    ws["C2"] = 4580
    ws["D2"] = 4590

    ws.merge_cells("A3:A4")
    ws["A3"] = "Long Seam Orientation (hh:mm)\n(2022 Rosen)\n(2025 TDW)"
    ws["B3"] = "11:28"
    ws["C3"] = "12:40"
    ws["D3"] = "11:22"
    ws["B4"] = "11:38"
    ws["C4"] = "12:56"
    ws["D4"] = "11:28"

    ws.merge_cells("A5:A6")
    ws["A5"] = "Joint Length (m)\n(2022 Rosen)\n(2025 TDW)"
    ws["B5"] = 19.560
    ws["C5"] = 18.860
    ws["D5"] = 19.340
    ws["B6"] = 19.650
    ws["C6"] = 18.910
    ws["D6"] = 19.394

    _, joint_df, metadata = parse_dig_package_excel(_workbook_bytes(workbook))

    assert metadata["joint_section_found"] is True
    assert joint_df is not None
    assert joint_df.iloc[0, 0] == "Long Seam Orientation (hh:mm)"
    assert joint_df.iloc[0, 1] == "2022 Rosen"
    assert joint_df.iloc[1, 1] == "2025 TDW"
    assert joint_df.iloc[2, 0] == "Joint Length (m)"
    assert list(joint_df.columns[:5]) == ["Metric", "Source", "4570", "4580", "4590"]


def test_parse_joint_summary_matrix_reads_sources_from_merged_label_block():
    joint_df = pd.DataFrame(
        [
            ["Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "11:28", "12:40", "11:22"],
            ["Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "11:38", "12:56", "11:28"],
            ["Joint Length (m) (2022 Rosen) (2025 TDW)", 19.560, 18.860, 19.340],
            ["Joint Length (m) (2022 Rosen) (2025 TDW)", 19.650, 18.910, 19.394],
        ],
        columns=["Girth Weld No.", "4570", "4580", "4590"],
    )

    parsed = _parse_joint_summary_matrix(joint_df, parse_orientation_to_hours, logger=dig_package_reader_logger)

    assert parsed is not None
    by_source = parsed["gwd_by_source"]
    assert set(by_source.keys()) == {"2022 Rosen", "2025 TDW"}
    assert by_source["2022 Rosen"][4580] == 12 + 40 / 60
    assert by_source["2025 TDW"][4580] == 12 + 56 / 60
    assert all(value <= 12.95 for seam_map in by_source.values() for value in seam_map.values())


def test_parse_joint_summary_matrix_interleaved_duplicate_column_headers():
    """PNG-style Joint Summary: two ILI columns per GWD (30900 / 30900__2), one longseam row."""
    joint_df = pd.DataFrame(
        [
            [
                "Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)",
                "10:40",
                "10:30",
                "10:45",
                "10:35",
            ],
            [
                "Joint Length (m) (2022 Rosen) (2025 TDW)",
                13.5,
                13.6,
                13.84,
                13.92,
            ],
        ],
        columns=["Metric", "30900", "30900__2", "30930", "30930__2"],
    )

    parsed = _parse_joint_summary_matrix(joint_df, parse_orientation_to_hours, logger=dig_package_reader_logger)

    assert parsed is not None
    by_source = parsed["gwd_by_source"]
    assert set(by_source.keys()) == {"2022 Rosen", "2025 TDW"}
    assert by_source["2022 Rosen"][30900] == 10 + 40 / 60
    assert by_source["2025 TDW"][30900] == 10 + 30 / 60
    assert by_source["2022 Rosen"][30930] == 10 + 45 / 60
    assert by_source["2025 TDW"][30930] == 10 + 35 / 60
    jl = parsed["joint_lengths"]
    assert jl[30900] == round((13.5 + 13.6) / 2, 2)
    assert jl[30930] == round((13.84 + 13.92) / 2, 2)


def test_reshape_joint_summary_dataframe_splits_metric_and_source():
    joint_df = pd.DataFrame(
        [
            ["Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "11:28", "12:40"],
            ["Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "Long Seam Orientation (hh:mm) (2022 Rosen) (2025 TDW)", "11:38", "12:56"],
            ["Joint Length (m) (2022 Rosen) (2025 TDW)", "Joint Length (m) (2022 Rosen) (2025 TDW)", 19.560, 18.860],
            ["Joint Length (m) (2022 Rosen) (2025 TDW)", "Joint Length (m) (2022 Rosen) (2025 TDW)", 19.650, 18.910],
        ],
        columns=["Girth Weld No.", "Girth Weld No.__2", "4570", "4580"],
    )

    reshaped = _reshape_joint_summary_dataframe(joint_df)

    assert list(reshaped.columns[:4]) == ["Metric", "Source", "4570", "4580"]
    assert reshaped.iloc[0, 0] == "Long Seam Orientation (hh:mm)"
    assert reshaped.iloc[0, 1] == "2022 Rosen"
    assert reshaped.iloc[1, 1] == "2025 TDW"
    assert reshaped.iloc[2, 0] == "Joint Length (m)"


def test_extract_sources_from_block_label_does_not_require_known_vendor_names():
    label = "Long Seam Orientation (hh:mm)\n(Alpha Tool)\n(Beta Inline 2027)"

    sources = _extract_sources_from_block_label(label)

    assert sources == ["Alpha Tool", "Beta Inline 2027"]


def test_match_joint_source_name_matches_joint_source_to_feature_source_generically():
    available = ["2022 Rosen", "2025 TDW"]

    assert _match_joint_source_name("2022 Rosen-MFLA", available) == "2022 Rosen"
    assert _match_joint_source_name("2022 Rosen EMAT", available) == "2022 Rosen"
    assert _match_joint_source_name("2025 TDW", available) == "2025 TDW"


def test_build_joint_context_returns_upstream_target_downstream_per_source():
    girth_welds = [
        {"chainage": -19.56, "gwd_number": 4570, "label": "GWD 4570", "source": "2022 Rosen-MFLA"},
        {"chainage": 0.0, "gwd_number": 4580, "label": "GWD 4580", "source": "2022 Rosen-MFLA"},
        {"chainage": 18.86, "gwd_number": 4590, "label": "GWD 4590", "source": "2022 Rosen-MFLA"},
    ]
    seam_map_by_joint_source = {
        "2022 Rosen": {4570: 11 + 28 / 60, 4580: 12 + 40 / 60, 4590: 11 + 22 / 60},
    }

    context = _build_joint_context(girth_welds, seam_map_by_joint_source, ["2022 Rosen-MFLA"])

    assert context["2022 Rosen-MFLA"]["joint_source"] == "2022 Rosen"
    assert context["2022 Rosen-MFLA"]["upstream"]["gwd_number"] == 4570
    assert context["2022 Rosen-MFLA"]["target"]["gwd_number"] == 4580
    assert context["2022 Rosen-MFLA"]["downstream"]["gwd_number"] == 4590
    assert context["2022 Rosen-MFLA"]["target"]["longseam_label"] == "12:40"


def test_build_feature_map_from_dig_package_returns_joint_summary_rows_and_context():
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Dig Package"
    ws["A1"] = "Joint Summary"
    ws["A2"] = "Girth Weld No."
    ws["B2"] = "Girth Weld No."
    ws["C2"] = 4570
    ws["D2"] = 4580
    ws["E2"] = 4590
    ws.merge_cells("A3:B3")
    ws["A3"] = "Long Seam Orientation (hh:mm)\n(2022 Rosen)\n(2025 TDW)"
    ws["C3"] = "11:28"
    ws["D3"] = "12:40"
    ws["E3"] = "11:22"
    ws.merge_cells("A4:B4")
    ws["A4"] = "Long Seam Orientation (hh:mm)\n(2022 Rosen)\n(2025 TDW)"
    ws["C4"] = "11:38"
    ws["D4"] = "12:56"
    ws["E4"] = "11:28"

    ws["A7"] = "Feature Summary"
    ws["A8"] = "Distance from TGW (m)"
    ws["B8"] = "Feature Type"
    ws["C8"] = "Joint Number"
    ws["D8"] = "ILI Source"
    ws["A9"] = -19.56
    ws["B9"] = "Girth Weld"
    ws["C9"] = 4570
    ws["D9"] = "2022 Rosen-MFLA"
    ws["A10"] = 0.0
    ws["B10"] = "Girth Weld"
    ws["C10"] = 4580
    ws["D10"] = "2022 Rosen-MFLA"
    ws["A11"] = 18.86
    ws["B11"] = "Girth Weld"
    ws["C11"] = 4590
    ws["D11"] = "2022 Rosen-MFLA"

    _, scatter_data, _, _, joint_summary_parsed, feature_summary_raw = build_feature_map_from_dig_package(_workbook_bytes(workbook))

    assert len(joint_summary_parsed) == 6
    ctx = scatter_data["joint_context_by_source"]["2022 Rosen-MFLA"]
    assert ctx["target"]["gwd_number"] == 4580
    assert ctx["upstream"]["longseam_label"] == "11:28"
    assert feature_summary_raw["joint_context_by_source"]["2022 Rosen-MFLA"]["downstream"]["gwd_number"] == 4590


def test_build_feature_map_tgw_layout_uses_joint_lengths_for_four_red_lines():
    """When Joint Summary has ≥4 GWDs + joint lengths, girth welds sit at 0 and ±joint lengths."""
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Dig Package"
    ws["A1"] = "Joint Summary"
    ws["A2"] = "Girth Weld No."
    ws["B2"] = "Girth Weld No."
    ws["C2"] = 4560
    ws["D2"] = 4570
    ws["E2"] = 4580
    ws["F2"] = 4590
    ws.merge_cells("A3:B3")
    ws["A3"] = "Long Seam Orientation (hh:mm)\n(2022 Rosen)\n(2025 TDW)"
    ws["C3"] = "10:00"
    ws["D3"] = "10:10"
    ws["E3"] = "10:20"
    ws["F3"] = "10:30"
    ws.merge_cells("A4:B4")
    ws["A4"] = "Long Seam Orientation (hh:mm)\n(2022 Rosen)\n(2025 TDW)"
    ws["C4"] = "10:05"
    ws["D4"] = "10:15"
    ws["E4"] = "10:25"
    ws["F4"] = "10:35"

    ws.merge_cells("A5:B5")
    ws["A5"] = "Joint Length (m)\n(2022 Rosen)\n(2025 TDW)"
    ws["C5"] = 12.0
    ws["D5"] = 17.5
    ws["E5"] = 19.0
    ws["F5"] = 18.5

    ws["A9"] = "Feature Summary"
    ws["A10"] = "Distance from TGW (m)"
    ws["B10"] = "Feature Type"
    ws["C10"] = "Joint Number"
    ws["D10"] = "ILI Source"
    ws["A11"] = -5.0
    ws["B11"] = "Metal Loss"
    ws["C11"] = 1
    ws["D11"] = "2022 Rosen-MFLA"

    _, scatter_data, _, _, _, _ = build_feature_map_from_dig_package(_workbook_bytes(workbook))

    assert scatter_data.get("joint_summary_tgw_layout") is True
    gws = sorted(scatter_data["girth_welds"], key=lambda g: g["chainage"])
    assert len(gws) == 4
    # Joint length under upstream GWD of each span: L(4560–4570)=12, L(4570–4580)=17.5, L(4580–4590)=19
    assert abs(gws[0]["chainage"] - (-12.0)) < 0.01
    assert abs(gws[1]["chainage"] - 0.0) < 0.01
    assert abs(gws[2]["chainage"] - 17.5) < 0.01
    assert abs(gws[3]["chainage"] - 36.5) < 0.01
    seams = scatter_data.get("seam_welds", [])
    assert len(seams) >= 3
    tol = 0.02

    def _has_span(a: float, b: float) -> bool:
        return any(
            abs(s["chainage_start"] - a) < tol and abs(s["chainage_end"] - b) < tol for s in seams
        )

    assert _has_span(-12.0, 0.0)
    assert _has_span(0.0, 17.5)


def test_find_header_row_after_skips_repeated_merged_section_title():
    workbook = Workbook()
    ws = workbook.active
    ws.title = "Dig Package"
    ws.merge_cells("A1:J1")
    ws["A1"] = "Feature Summary"
    ws["A2"] = "Distance from TGW (m)"
    ws["B2"] = "Feature ID"
    ws["C2"] = "Depth (%)"
    ws["A3"] = 0.0
    ws["B3"] = "F-1"
    ws["C3"] = 25

    header_row = _find_header_row_after(ws, 1)

    assert header_row == 2
