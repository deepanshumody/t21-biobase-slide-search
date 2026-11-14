#!/usr/bin/env bash
# Re-download the PUBLIC data used by the TCGA validation (not committed to Git; ~100 MB).
#   bash fetch_public_data.sh            # from the concordance/ folder
# Sources: TCGA-Reports (Kefeli & Tatonetti 2024, MIT) and the cBioPortal public API.
# The Biobase challenge pack is NOT downloaded here: get it through the event's access process
# and unzip it so that criteria_search/pack_reports/ exists (see README.md).
set -euo pipefail
cd "$(dirname "$0")"

B=concordance_breast/data/raw
C=concordance_colon/data/raw
mkdir -p "$B" "$C"

echo "TCGA-Reports (OCR'd TCGA pathology reports)"
curl -sfL -o "$B/TCGA_Reports.csv.zip" \
  https://raw.githubusercontent.com/tatonetti-lab/tcga-path-reports/main/TCGA_Reports.csv.zip
unzip -q -o "$B/TCGA_Reports.csv.zip" TCGA_Reports.csv -d "$B"
ln -sf ../../../concordance_breast/data/raw/TCGA_Reports.csv "$C/TCGA_Reports.csv"

echo "cBioPortal clinical labels (breast: brca_tcga, colorectal: coadread_tcga)"
API='https://www.cbioportal.org/api/studies'
curl -sfL -o "$B/brca_tcga_clinical_patient.json" \
  "$API/brca_tcga/clinical-data?clinicalDataType=PATIENT&projection=SUMMARY&pageSize=10000000"
curl -sfL -o "$C/coadread_tcga_clinical_patient.json" \
  "$API/coadread_tcga/clinical-data?clinicalDataType=PATIENT&projection=SUMMARY&pageSize=10000000"

echo "Linking reports to labels"
python3 concordance_breast/scripts/build_linked.py
python3 concordance_colon/build_linked.py

echo "Optional: TREC Clinical Trials 2021/2022 topics + judgments (trial_twins)"
T=trial_twins/trec/raw
mkdir -p "$T"
for y in 2021 2022; do
  curl -sfL -o "$T/topics$y.xml" "https://www.trec-cds.org/topics$y.xml" || true
  curl -sfL -o "$T/qrels$y.txt" "https://trec.nist.gov/data/trials/qrels$y.txt" || true
done
echo "done"
