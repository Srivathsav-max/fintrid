import streamlit as st
import requests
import pandas as pd
from typing import List, Dict

API_BASE_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Fintrid - TRID Tolerance Checker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_api_health() -> bool:
    try:
        r = requests.get(f"{API_BASE_URL}/api/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def upload_and_extract(le_file, cd_file) -> str:
    files = {"le": le_file, "cd": cd_file}
    r = requests.post(f"{API_BASE_URL}/api/extract", files=files)
    r.raise_for_status()
    return r.json()["loan_id"]

def fetch_fees_df(loan_id: str) -> pd.DataFrame:
    r = requests.get(f"{API_BASE_URL}/api/fees", params={"loan_id": loan_id})
    r.raise_for_status()
    data = r.json()
    return pd.DataFrame(data)

def fetch_fees_raw(loan_id: str):
    r = requests.get(f"{API_BASE_URL}/api/fees", params={"loan_id": loan_id})
    r.raise_for_status()
    return r.json()

def annotate_fees(payload: List[Dict]):
    r = requests.post(f"{API_BASE_URL}/api/annotate", json=payload)
    r.raise_for_status()
    return r.json()

def validate(loan_id: str) -> Dict:
    r = requests.get(f"{API_BASE_URL}/api/validate", params={"loan_id": loan_id})
    r.raise_for_status()
    return r.json()

def get_cure_letter_html(loan_id: str) -> str:
    r = requests.get(f"{API_BASE_URL}/api/cure-letter", params={"loan_id": loan_id})
    r.raise_for_status()
    return r.json()["html"]

def _has_cols(df: pd.DataFrame, cols: List[str]) -> bool:
    return set(cols).issubset(df.columns)

def main():
    st.title("💰 Fintrid - TRID Tolerance Checker (LE vs CD)")

    if not check_api_health():
        st.error("API is not running! Please start the FastAPI server first.")
        st.code("uv run fintrid-api", language="bash")
        st.stop()

    st.success("Connected to API")

    tab1, tab2, tab3 = st.tabs(["1) Upload PDFs", "2) Review & Validate", "3) Cure Letter"])

    with tab1:
        st.subheader("Upload Loan Estimate (LE) and Closing Disclosure (CD)")
        le = st.file_uploader("Loan Estimate (LE.pdf)", type=["pdf"], key="le_upl")
        cd = st.file_uploader("Closing Disclosure (CD.pdf)", type=["pdf"], key="cd_upl")

        if st.button("Extract & Parse"):
            if not (le and cd):
                st.warning("Please upload both LE.pdf and CD.pdf")
            else:
                try:
                    loan_id = upload_and_extract(le, cd)
                    st.session_state["loan_id"] = loan_id
                    st.success(f"Parsed PDF(s). Loan ID: {loan_id}")
                except requests.HTTPError as e:
                    st.error(f"Extract failed: {e.response.text}")
                except Exception as e:
                    st.exception(e)

        st.caption("Tip: If OCR isn’t configured, the backend falls back to PyMuPDF text extraction.")

    with tab2:
        st.subheader("Review fee rows, set flags, and validate")
        loan_id = st.session_state.get("loan_id")
        if not loan_id:
            st.info("Upload PDFs first (tab 1).")
        else:
            try:
                df = fetch_fees_df(loan_id)
            except requests.HTTPError as e:
                st.error(f"/api/fees failed: {e.response.text}")
                return
            except Exception as e:
                st.exception(e)
                return

            if df.empty or not _has_cols(df, ["source"]):
                st.warning("No fee rows were parsed from the PDFs. This can happen if OCR/text extraction failed or the document layout is unusual.")
                with st.expander("Show raw /api/fees response"):
                    st.json(fetch_fees_raw(loan_id))
                st.info(
                    "Try again with CFPB specimen forms or enable OCR:\n"
                    "• Ensure `.env` has LANDINGAI_API_KEY\n"
                    "• If using pdf2image OCR path, install Poppler: `brew install poppler`"
                )
                return

            # Side-by-side LE/CD views
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("**Loan Estimate (LE) fees**")
                le_df = df[df["source"] == "LE"].copy()
                if le_df.empty:
                    st.info("No LE rows parsed.")
                else:
                    st.dataframe(
                        le_df[["section", "line_label", "description", "amount_borrower_at_close", "bucket_hint"]]
                        .reset_index(drop=True),
                        use_container_width=True
                    )

            with c2:
                st.markdown("**Closing Disclosure (CD) fees**")
                cd_df = df[df["source"] == "CD"].copy()
                if cd_df.empty:
                    st.info("No CD rows parsed.")
                else:
                    st.dataframe(
                        cd_df[["section", "line_label", "description", "amount_borrower_at_close", "bucket_hint"]]
                        .reset_index(drop=True),
                        use_container_width=True
                    )

            if "id" not in df.columns:
                st.warning("Parsed rows lack IDs; skipping flag editor.")
                return

            st.markdown("---")
            st.markdown("### Adjust Flags (affects tolerance bucket)")
            st.caption("Toggle **affiliate**, **shoppable**, **chosen_from_list** for LE rows.")

            payload: List[Dict] = []
            if not le_df.empty:
                for _, row in le_df.iterrows():
                    with st.expander(f"{row.get('section', '')} - {row.get('description','')}"):
                        col1, col2, col3, col4 = st.columns(4)
                        affiliate_val = col1.checkbox("Affiliate", value=bool(row.get("affiliate", False)), key=f"aff_{row['id']}")
                        shoppable_val = col2.checkbox("Shoppable", value=bool(row.get("shoppable", False)), key=f"shop_{row['id']}")
                        chosen_val = col3.checkbox("Chosen from list", value=bool(row.get("chosen_from_list", False)), key=f"list_{row['id']}")
                        col4.write(f"Bucket hint: **{row.get('bucket_hint') or 'auto'}**")
                        payload.append({
                            "fee_id": row["id"],
                            "affiliate": affiliate_val,
                            "shoppable": shoppable_val,
                            "chosen_from_list": chosen_val
                        })

                if st.button("Apply Flag Changes"):
                    try:
                        annotate_fees(payload)
                        st.success("Updated. Re-run validation below.")
                    except Exception as e:
                        st.exception(e)

            st.markdown("### Validate")
            if st.button("Run Validation"):
                try:
                    res = validate(loan_id)
                    st.metric("10% Bucket Overage", f"${res['ten_bucket_overage']:.2f}")
                    st.metric("Total Cure", f"${res['cure_total']:.2f}")
                    st.markdown("**0% Overages**")
                    st.dataframe(pd.DataFrame(res["zero_overages"]))
                    st.markdown("**10% Bucket Details**")
                    st.dataframe(pd.DataFrame(res["ten_bucket_details"]))
                except requests.HTTPError as e:
                    st.error(f"/api/validate failed: {e.response.text}")
                except Exception as e:
                    st.exception(e)

    with tab3:
        st.subheader("Generate Cure Letter")
        loan_id = st.session_state.get("loan_id")
        if not loan_id:
            st.info("Upload PDFs first.")
        else:
            if st.button("Generate Cure Letter (HTML)"):
                try:
                    html = get_cure_letter_html(loan_id)
                    st.download_button(
                        "Download Cure Letter",
                        data=html.encode("utf-8"),
                        file_name="cure_letter.html",
                        mime="text/html"
                    )
                    st.success("Cure letter ready.")
                except requests.HTTPError as e:
                    st.error(f"/api/cure-letter failed: {e.response.text}")
                except Exception as e:
                    st.exception(e)

if __name__ == "__main__":
    main()