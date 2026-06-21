from __future__ import annotations

import pandas as pd
import streamlit as st

from factcheck import (
    extract_candidate_claims,
    extract_pdf_text,
    generate_markdown_report,
    reports_to_csv,
    verify_claim,
)


st.set_page_config(page_title="Fact-Check Agent", page_icon="check", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      [data-testid="stMetric"] {
        background: #f7f7f2;
        border: 1px solid #deded3;
        padding: 14px 16px;
        color: #18231f;
      }
      [data-testid="stMetric"] * {color: #18231f !important;}
      [data-testid="stMetricLabel"] {font-size: 0.85rem;}
      .status-verified {color: #0f766e; font-weight: 700;}
      .status-inaccurate {color: #b45309; font-weight: 700;}
      .status-false {color: #b91c1c; font-weight: 700;}
      .status-search-unavailable {color: #64748b; font-weight: 700;}
      .source-link {font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Fact-Check Agent")

with st.sidebar:
    uploaded_pdf = st.file_uploader("PDF", type=["pdf"])
    max_claims = st.slider("Claims", min_value=3, max_value=20, value=10)
    max_results = st.slider("Sources per claim", min_value=3, max_value=10, value=6)
    run_check = st.button("Run check", type="primary", use_container_width=True)


def _status_class(status: str) -> str:
    return {
        "Verified": "status-verified",
        "Inaccurate": "status-inaccurate",
        "False": "status-false",
        "Search unavailable": "status-search-unavailable",
    }.get(status, "")


if not uploaded_pdf:
    st.info("Upload a PDF to extract and verify claims.")
    st.stop()

try:
    pdf_text = extract_pdf_text(uploaded_pdf)
except Exception as exc:
    st.error(f"Could not read the PDF: {exc}")
    st.stop()

if not pdf_text:
    st.warning("No extractable text found in this PDF.")
    st.stop()

claims = extract_candidate_claims(pdf_text, max_claims=max_claims)

left, right = st.columns([0.36, 0.64], gap="large")
with left:
    st.subheader("Extracted Claims")
    if claims:
        for index, claim in enumerate(claims, start=1):
            st.caption(f"{index}. {claim}")
    else:
        st.warning("No quantified claims were detected.")

with right:
    st.subheader("Document Preview")
    st.text_area("Text", pdf_text[:4000], height=260, label_visibility="collapsed")

if not run_check:
    st.stop()

if not claims:
    st.stop()

progress = st.progress(0)
status_line = st.empty()
reports = []

for index, claim in enumerate(claims, start=1):
    status_line.write(f"Checking claim {index} of {len(claims)}")
    reports.append(verify_claim(claim, max_results=max_results))
    progress.progress(index / len(claims))

status_line.empty()

summary = {
    status: sum(1 for report in reports if report.status == status)
    for status in ("Verified", "Inaccurate", "False", "Search unavailable")
}
metrics = st.columns(4)
metrics[0].metric("Verified", summary["Verified"])
metrics[1].metric("Inaccurate", summary["Inaccurate"])
metrics[2].metric("False / no evidence", summary["False"])
metrics[3].metric("Search unavailable", summary["Search unavailable"])

rows = [report.to_row() for report in reports]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

for index, report in enumerate(reports, start=1):
    with st.expander(f"{index}. {report.status} - {report.claim[:110]}"):
        st.markdown(f"<span class='{_status_class(report.status)}'>{report.status}</span> | Confidence {report.confidence:.2f}", unsafe_allow_html=True)
        st.write(report.correction)
        if report.matched_quantities:
            st.write("Matched quantities:", ", ".join(report.matched_quantities))
        if report.alternative_quantities:
            st.write("Alternative figures/dates:", ", ".join(report.alternative_quantities))
        st.caption(f"Search query: {report.query}")
        for item in report.evidence:
            st.markdown(f"<div class='source-link'><a href='{item.url}' target='_blank'>{item.title}</a><br>{item.snippet}</div>", unsafe_allow_html=True)

report_md = generate_markdown_report(reports)
report_csv = reports_to_csv(reports)

download_col_1, download_col_2 = st.columns(2)
download_col_1.download_button("Download report", report_md, file_name="fact_check_report.md", mime="text/markdown", use_container_width=True)
download_col_2.download_button("Download CSV", report_csv, file_name="fact_check_report.csv", mime="text/csv", use_container_width=True)
