"""
Fetch candidate trials from the public ClinicalTrials.gov API v2 (generic condition queries only;
no patient data is sent). Saves raw records to trials/raw/ and prints a shortlist scored by how
many pathology facts the eligibility text uses.   python3 fetch_trials.py
See trial_matching_design.md, section 4.
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "trials", "raw")
API = "https://clinicaltrials.gov/api/v2/studies"
CONDITIONS = {"breast": "breast cancer", "colon": "colon cancer", "lung": "non-small cell lung cancer",
              "prostate": "prostate cancer", "stomach": "gastric cancer", "kidney": "renal cell carcinoma",
              "skin": "melanoma"}
# Pathology facts the profile holds -> words that show a trial uses them.
PATH_TERMS = r"HER2|estrogen|progesterone|hormone receptor|\bER\b|node|N[0-3]\b|T[1-4]\b|stage I|grade|Gleason|" \
             r"histolog|adenocarcinoma|squamous|clear cell|resect|margin|lymphovascular|Breslow|mucinous|ISUP"


def fetch(organ, cond, n=40):
    q = {"query.cond": cond, "filter.overallStatus": "RECRUITING", "query.term": "AREA[StudyType]INTERVENTIONAL",
         "pageSize": n, "format": "json",
         "fields": "NCTId,BriefTitle,Phase,OverallStatus,EligibilityModule,StartDate,EnrollmentInfo"}
    url = API + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": "trial-matching-research/0.1"})
    return json.load(urllib.request.urlopen(req, timeout=60)).get("studies", [])


def main():
    today = datetime.date.today().isoformat()
    for organ, cond in CONDITIONS.items():
        studies = fetch(organ, cond)
        scored = []
        for s in studies:
            ps = s.get("protocolSection", {})
            nct = ps.get("identificationModule", {}).get("nctId")
            elig = ps.get("eligibilityModule", {}).get("eligibilityCriteria", "") or ""
            phases = ps.get("designModule", {}).get("phases", [])
            hits = sorted(set(m.group(0) for m in re.finditer(PATH_TERMS, elig)))
            rec = {"nct": nct, "organ": organ, "fetched": today, "title": ps.get("identificationModule", {}).get("briefTitle"),
                   "phases": phases, "eligibility": elig, "path_terms": hits}
            json.dump(rec, open(os.path.join(RAW, f"{nct}.json"), "w"), indent=1)
            scored.append((len(hits), len(elig), rec))
        scored.sort(key=lambda x: (-x[0], x[1]))
        print(f"\n=== {organ} ({len(studies)} recruiting interventional)")
        for k, L, r in scored[:6]:
            print(f"  {r['nct']} {','.join(r['phases']) or '-':14} terms={k:2} chars={L:5}  {r['title'][:85]}")


if __name__ == "__main__":
    main()
